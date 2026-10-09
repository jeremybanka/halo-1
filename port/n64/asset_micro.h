#ifndef BG_ASSET_MICRO_H
#define BG_ASSET_MICRO_H
#include "asset_models.h"
/* Additional tiny far-model tables; original model tables remain linked.
 * Absent candidates alias the original far asset, not a zero-sized mesh. */
extern const bg_model_asset *const bg_vehicle_micro_lods[4];
extern const bg_model_asset *const bg_pickup_micro_lods[BG_M_COUNT];
/* Original bounds union candidate quantized points. Runtime still unions every
 * current articulated near vehicle part before culling or projection gates. */
extern const bg_bounds bg_vehicle_micro_gate_bounds[4];
extern const bg_bounds bg_pickup_micro_gate_bounds[BG_M_COUNT];
#endif
