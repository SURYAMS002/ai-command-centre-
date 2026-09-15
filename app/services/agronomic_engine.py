import math
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

# ------------------------------------------------------------------------------
# FAO-56 Agronomic Parameter Matrices & Reference Tables
# ------------------------------------------------------------------------------

# Soil Type Properties: Permanent Wilting Point (PWP %), Field Capacity (FC %), Infiltration Rate (mm/hr)
SOIL_PROPERTIES: Dict[str, Dict[str, Any]] = {
    "Sandy": {
        "pwp_pct": 10.0,
        "fc_pct": 22.0,
        "default_ph": 6.2,
        "infiltration": "High",
        "description": "Coarse-textured soil with rapid drainage and low water holding capacity."
    },
    "Loamy": {
        "pwp_pct": 15.0,
        "fc_pct": 32.0,
        "default_ph": 6.8,
        "infiltration": "Medium",
        "description": "Optimal balanced soil mixture of sand, silt, and clay with good retention."
    },
    "Clay": {
        "pwp_pct": 26.0,
        "fc_pct": 48.0,
        "default_ph": 7.2,
        "infiltration": "Low",
        "description": "Fine-textured soil with high moisture retention and slow water movement."
    },
    "Silt": {
        "pwp_pct": 18.0,
        "fc_pct": 36.0,
        "default_ph": 6.5,
        "infiltration": "Medium",
        "description": "Smooth, fertile soil particles with high nutrient and moisture storage."
    },
    "Peat": {
        "pwp_pct": 30.0,
        "fc_pct": 55.0,
        "default_ph": 5.5,
        "infiltration": "High-Retention",
        "description": "Organic-rich soil with very high water retention and acidic pH."
    },
    "Saline": {
        "pwp_pct": 20.0,
        "fc_pct": 38.0,
        "default_ph": 8.1,
        "infiltration": "Low-Medium",
        "description": "High soluble salt content requiring higher osmotic leaching fraction."
    }
}

# Crop Growth Stage Soil Depletion Multipliers (MAD = Maximum Allowable Depletion 0.0 - 1.0)
CROP_AGRONOMIC_PROPERTIES: Dict[str, Dict[str, Any]] = {
    "Tomato": {
        "mad": 0.40,  # Sensitive to water stress
        "optimal_ph": (6.0, 7.0),
        "npk_target": {"n": 150.0, "p": 60.0, "k": 200.0},
        "stage_mad_modifiers": {
            "Initial/Vegetative": 0.50,
            "Flowering": 0.35,  # Highly critical flowering stage
            "Yield Formation": 0.40,
            "Maturity": 0.55
        }
    },
    "Rice": {
        "mad": 0.20,  # Requires high moisture / semi-submerged conditions
        "optimal_ph": (5.5, 6.5),
        "npk_target": {"n": 180.0, "p": 40.0, "k": 120.0},
        "stage_mad_modifiers": {
            "Initial/Vegetative": 0.20,
            "Flowering": 0.15,
            "Yield Formation": 0.25,
            "Maturity": 0.45
        }
    },
    "Wheat": {
        "mad": 0.55,
        "optimal_ph": (6.0, 7.5),
        "npk_target": {"n": 120.0, "p": 50.0, "k": 100.0},
        "stage_mad_modifiers": {
            "Initial/Vegetative": 0.60,
            "Flowering": 0.45,
            "Yield Formation": 0.50,
            "Maturity": 0.65
        }
    },
    "Cotton": {
        "mad": 0.65,  # Deep-rooted, drought tolerant
        "optimal_ph": (5.8, 8.0),
        "npk_target": {"n": 140.0, "p": 55.0, "k": 150.0},
        "stage_mad_modifiers": {
            "Initial/Vegetative": 0.65,
            "Flowering": 0.50,
            "Yield Formation": 0.60,
            "Maturity": 0.75
        }
    },
    "Maize": {
        "mad": 0.50,
        "optimal_ph": (5.8, 7.2),
        "npk_target": {"n": 160.0, "p": 65.0, "k": 140.0},
        "stage_mad_modifiers": {
            "Initial/Vegetative": 0.55,
            "Flowering": 0.40,
            "Yield Formation": 0.50,
            "Maturity": 0.60
        }
    },
    "Sugarcane": {
        "mad": 0.50,
        "optimal_ph": (6.0, 7.5),
        "npk_target": {"n": 220.0, "p": 80.0, "k": 240.0},
        "stage_mad_modifiers": {
            "Initial/Vegetative": 0.50,
            "Flowering": 0.45,
            "Yield Formation": 0.45,
            "Maturity": 0.65
        }
    }
}


class AgronomicProfile(BaseModel):
    soil_type: str
    crop: str
    growth_stage: str
    pwp_pct: float
    fc_pct: float
    optimal_moisture_threshold_pct: float
    ph_level: float
    nitrogen_ppm: float
    phosphorus_ppm: float
    potassium_ppm: float
    npk_status: str
    rationale: str


class AgronomicParameterEngine:
    """
    FAO-56 Standard Dynamic Agronomic Imputation & Threshold Engine.
    Imputes missing soil parameters and dynamically calculates field-specific
    moisture depletion thresholds based on Soil Type, Crop, and Growth Stage.
    """

    @staticmethod
    def get_soil_properties(soil_type: str) -> Dict[str, Any]:
        normalized_soil = soil_type.capitalize()
        return SOIL_PROPERTIES.get(normalized_soil, SOIL_PROPERTIES["Loamy"])

    @staticmethod
    def get_crop_properties(crop: str) -> Dict[str, Any]:
        normalized_crop = crop.capitalize()
        return CROP_AGRONOMIC_PROPERTIES.get(normalized_crop, CROP_AGRONOMIC_PROPERTIES["Tomato"])

    @classmethod
    def calculate_optimal_moisture_threshold(
        cls,
        soil_type: str,
        crop: str,
        growth_stage: str = "Vegetative"
    ) -> Dict[str, float]:
        """
        Dynamically calculates optimal moisture depletion threshold:
        Threshold (%) = PWP + (FC - PWP) * (1 - MAD)
        """
        soil_info = cls.get_soil_properties(soil_type)
        crop_info = cls.get_crop_properties(crop)

        pwp = soil_info["pwp_pct"]
        fc = soil_info["fc_pct"]

        # Determine MAD modifier based on growth stage
        stage_modifiers = crop_info.get("stage_mad_modifiers", {})
        mad = stage_modifiers.get(growth_stage, crop_info.get("mad", 0.50))

        # Dynamic Threshold calculation
        threshold_pct = round(pwp + (fc - pwp) * (1.0 - mad), 1)

        return {
            "pwp_pct": pwp,
            "fc_pct": fc,
            "mad": mad,
            "threshold_pct": threshold_pct
        }

    @classmethod
    def impute_field_parameters(
        cls,
        soil_type: Optional[str] = "Loamy",
        crop: Optional[str] = "Tomato",
        growth_stage: Optional[str] = "Vegetative",
        ph_level: Optional[float] = None,
        nitrogen_ppm: Optional[float] = None,
        phosphorus_ppm: Optional[float] = None,
        potassium_ppm: Optional[float] = None,
    ) -> AgronomicProfile:
        """
        Imputes missing parameters for a field based on soil classification
        and agronomic targets.
        """
        s_type = soil_type if soil_type in SOIL_PROPERTIES else "Loamy"
        c_type = crop if crop in CROP_AGRONOMIC_PROPERTIES else "Tomato"
        g_stage = growth_stage or "Vegetative"

        soil_info = cls.get_soil_properties(s_type)
        crop_info = cls.get_crop_properties(c_type)

        calc = cls.calculate_optimal_moisture_threshold(s_type, c_type, g_stage)

        # Impute pH if missing
        imputed_ph = ph_level if ph_level is not None else soil_info["default_ph"]

        # Impute NPK if missing
        target_npk = crop_info["npk_target"]
        imputed_n = nitrogen_ppm if nitrogen_ppm is not None else target_npk["n"]
        imputed_p = phosphorus_ppm if phosphorus_ppm is not None else target_npk["p"]
        imputed_k = potassium_ppm if potassium_ppm is not None else target_npk["k"]

        # Check NPK Status
        npk_ratio = (imputed_n / target_npk["n"] + imputed_p / target_npk["p"] + imputed_k / target_npk["k"]) / 3.0
        if npk_ratio >= 0.95:
            npk_status = "Optimal"
        elif npk_ratio >= 0.75:
            npk_status = "Moderate Deficit"
        else:
            npk_status = "Severe Deficit"

        rationale = (
            f"Soil '{s_type}' (Wilting Point {calc['pwp_pct']}%, Field Capacity {calc['fc_pct']}%) "
            f"paired with crop '{c_type}' at stage '{g_stage}' (MAD {calc['mad']}). "
            f"Dynamic Irrigation Threshold set to {calc['threshold_pct']}%. "
            f"NPK Status: {npk_status} (pH {imputed_ph})."
        )

        return AgronomicProfile(
            soil_type=s_type,
            crop=c_type,
            growth_stage=g_stage,
            pwp_pct=calc["pwp_pct"],
            fc_pct=calc["fc_pct"],
            optimal_moisture_threshold_pct=calc["threshold_pct"],
            ph_level=round(imputed_ph, 2),
            nitrogen_ppm=round(imputed_n, 1),
            phosphorus_ppm=round(imputed_p, 1),
            potassium_ppm=round(imputed_k, 1),
            npk_status=npk_status,
            rationale=rationale
        )
