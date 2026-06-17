# Sensor Skill Lifecycle State Machine

Reference: [CALIBRATION_LIFECYCLE_RESEARCH.md](../../CALIBRATION_LIFECYCLE_RESEARCH.md) — 1102-line research report with 36 citations.

## Three-layer architecture

```
LAYER 1  amb_w_spc · Sensor Skill           TEMPLATE (GitHub, GAMP 5 Cat 5)
LAYER 2  amb_w_spc · Sensor Configuration   INSTANCE per Company (lifecycle 0→9)
LAYER 3  raven_ai_agent · AI Skill Registry RUNTIME (only state=6 gated)
```

## 9-State Machine

| ID | Label | Semantics | E-sig? |
|---|---|---|---|
| 0 | Template | Code in GitHub, no instance | — |
| 1 | Provisioned | Hardware wired, comms verified | — |
| 2 | Configured | Scaling/offset/thresholds set | — |
| 3 | Calibrated | As-Found/As-Left recorded | Author |
| 4 | Tested | Auto tests passed, shadow-mode eligible | Reviewer |
| 5 | Approved | QA e-signature applied | **§11.50** |
| 6 | Certified | Release e-sig, dispatched by SkillRouter | **§11.50** |
| 7 | Suspended (reserved) | Non-terminal investigation pause | E-sig |
| 8 | Failed (reserved) | Terminal qual failure | E-sig |
| 9 | Retired | Planned EOL, immutable | E-sig |

## Non-negotiable rules

- **SkillRouter gate**: `lifecycle_state=6 AND calibration_due>=today() AND template_drift IN ("None","Minor")`
- **Per-Company independence**: Each Company (Juice / Dry / Mix / Laboratory / Formulated / AMB-Wellness parent) runs its own IQ/OQ/PQ. No auto-propagation across Companies.
- **Reverse transitions** (6→3, 6→2, 6→7, etc.): All require e-sig + `qualification_cycle_number` increment.
- **Shadow mode** at state=4: `shadow_mode_enabled=1` lets bot invoke skill but suppresses downstream action.
- **Immutability**: `Sensor Skill Lifecycle Transition` records cannot be deleted except by Administrator.

## DocType inventory (this PR)

### Modified
- **`Sensor Configuration`** — +15 fields (lifecycle_section through calibration_events table)
- **`Sensor Skill`** — +8 fields (template_governance_section through change_control table)

### New
- **`Sensor Skill Calibration Event`** — child of Sensor Configuration, ISO 17025 §7.8 compliant
- **`Sensor Skill Lifecycle Transition`** — immutable lifecycle transition log (supplements SPC Audit Trail)

## Reuse map (no duplication)

| Concern | Reused DocType |
|---|---|
| Audit trail | `SPC Audit Trail` |
| Electronic signatures | `SPC Electronic Signature` |
| Change control | `SPC Change Control` (child table on template) |
| Reference standards | `SPC Equipment` |
| Deviations | `SPC Deviation` |
| Process capability | `SPC Process Capability` |
| Multi-Company | Frappe `Company` (AMB-Wellness parent + 5 BUs) |

## Migration / Transport

**SANDBOX-FIRST**: Patch `v16/01_seed_sensor_lifecycle.py` only seeds data on sandbox sites (`v2.sysmayal.cloud`, `vm3.sysmayal.cloud`). TEST (`test.sysmayal2.cloud`) and PROD (`erp.sysmayal2.cloud`) get manual fixture imports per Company **after smoke passes at each tier**.

### Seed contents

**4 templates** (all GAMP 5 Cat 5):
- `scale_modbus_rtu_500kg` v0.1.0 (Released)
- `scale_serial_lab_30kg` v0.2.0 (Released)
- `ntc_thermistor_nano` v0.1.0 (Released)
- `soil_moisture_capacitive` v0.1.0 (Draft)

**8 instances** seeded at `lifecycle_state=1 Provisioned`:
- Plant fleet: `scale_juice` (Juice), `scale_dry` (Dry), `scale_mix` (Mix), `scale_formulated` (Formulated), `scale_lab` (Laboratory)
- Dev: `dev_l01_ntc_nano_01`, `dev_l01_ntc_nano_02`, `dev_l01_soil` (all AMB-Wellness)

## Rollout phases

| Phase | Site | Bench command |
|---|---|---|
| P1 | VM3 sandbox | `bench --site v2.sysmayal.cloud migrate` |
| P2 | VM3 — walk 1 instance 1→6 end-to-end | manual UI + signatures |
| P3 | VPT | `bench --site test.sysmayal2.cloud migrate` (after P2 passes) |
| P4 | VPP PROD | `bench --site erp.sysmayal2.cloud migrate` (after P3 passes, with confirmation) |

## References

- ISO/IEC 17025:2017 §7.8 (calibration certificate fields)
- 21 CFR Part 11 §11.50 (electronic signatures), §11.100 (no batch signing)
- GAMP 5 2nd Ed. (V-model: URS / FS / DS / IQ / OQ / PQ)
- ISA-95 Part 4 (equipment state per site)
- MLflow Model Registry (Production gating, shadow eval at Staging)
