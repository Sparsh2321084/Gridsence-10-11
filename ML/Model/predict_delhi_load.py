import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

class MultiEntityITransformer(nn.Module):
    def __init__(self, n_targets=7, n_exog=29, lookback=672, horizon=96, d_model=256, n_heads=8, n_layers=3, dropout=0.1):
        super().__init__()
        self.n_targets = n_targets
        self.target_embed = nn.Linear(lookback, d_model)
        self.exog_embed   = nn.Linear(lookback + horizon, d_model)
        self.token_type_emb = nn.Parameter(torch.randn(1, n_targets + n_exog, d_model) * 0.02)
        enc_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=d_model * 2,
            dropout=dropout, activation="gelu", batch_first=True, norm_first=True
        )
        self.encoder = nn.TransformerEncoder(enc_layer, num_layers=n_layers)
        self.proj_head = nn.Sequential(nn.LayerNorm(d_model), nn.Linear(d_model, horizon))

    def forward(self, y_hist, x_hist, x_fut):
        t_tokens = self.target_embed(y_hist.transpose(1, 2))
        x_all    = torch.cat([x_hist, x_fut], dim=1).transpose(1, 2)
        e_tokens = self.exog_embed(x_all)
        tokens   = torch.cat([t_tokens, e_tokens], dim=1) + self.token_type_emb
        encoded  = self.encoder(tokens)
        return self.proj_head(encoded[:, :self.n_targets, :]).transpose(1, 2)

def forecast_next_24h(bundle_path, y_hist_672x7, x_hist_672x29, x_fut_96x29, future_timestamps, recent_14d_block_bias=None):
    bundle = joblib.load(bundle_path)
    model = MultiEntityITransformer()
    model.load_state_dict(bundle["model_state_dict"])
    model.eval()

    yh = (y_hist_672x7 - bundle["y_mean"]) / bundle["y_std"]
    xh = bundle["x_scaler"].transform(x_hist_672x29)
    xf = bundle["x_scaler"].transform(x_fut_96x29)

    with torch.no_grad():
        pred_s = model(
            torch.tensor(yh[None], dtype=torch.float32),
            torch.tensor(xh[None], dtype=torch.float32),
            torch.tensor(xf[None], dtype=torch.float32),
        ).numpy()[0]

    pred_mw = pd.DataFrame(pred_s * bundle["y_std"] + bundle["y_mean"], index=future_timestamps, columns=bundle["all_targets"])

    # Apply causal block-of-day drift correction if trailing 14-day residuals are provided
    if recent_14d_block_bias is not None:
        pred_mw = pred_mw + 0.75 * recent_14d_block_bias

    # Coherent bottom-up reconciliation
    utils = bundle["utilities"]
    ratio = pred_mw["delhi_total_mw"] / pred_mw[utils].sum(axis=1)
    for u in utils:
        pred_mw[u] = (pred_mw[u] * ratio).clip(lower=0.0)

    # Attach ACI P05 / P95 uncertainty bounds
    for col, hw in bundle["aci_half_width_mw"].items():
        pred_mw[f"{col}_p05"] = (pred_mw[col] - hw).clip(lower=0.0)
        pred_mw[f"{col}_p95"] = pred_mw[col] + hw

    return pred_mw
