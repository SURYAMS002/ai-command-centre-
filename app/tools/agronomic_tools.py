from pathlib import Path
from typing import Dict, Any, Optional
from app.database.database import get_connection
from app.services.agronomic_engine import AgronomicParameterEngine

def get_soil_crop_parameters(field_name: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Returns dynamic agronomic soil & crop telemetry for a specified field,
    including soil type, crop, growth stage, NPK levels, pH, PWP, Field Capacity, and optimal threshold.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fields WHERE LOWER(name) = LOWER(?);", (field_name,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": f"Field '{field_name}' not found in farm database."}

    field = dict(row)
    s_type = field.get("soil_type", "Loamy")
    crop = field.get("crop", "Tomato")
    growth_stage = field.get("growth_stage", "Vegetative")

    profile = AgronomicParameterEngine.impute_field_parameters(
        soil_type=s_type,
        crop=crop,
        growth_stage=growth_stage,
        ph_level=field.get("ph_level"),
        nitrogen_ppm=field.get("nitrogen_ppm"),
        phosphorus_ppm=field.get("phosphorus_ppm"),
        potassium_ppm=field.get("potassium_ppm")
    )

    return {
        "field_name": field["name"],
        "crop": crop,
        "soil_type": s_type,
        "growth_stage": growth_stage,
        "current_soil_moisture_pct": field["soil_moisture_pct"],
        "wilting_point_pct": profile.pwp_pct,
        "field_capacity_pct": profile.fc_pct,
        "optimal_moisture_threshold_pct": profile.optimal_moisture_threshold_pct,
        "ph_level": profile.ph_level,
        "npk": {
            "nitrogen_ppm": profile.nitrogen_ppm,
            "phosphorus_ppm": profile.phosphorus_ppm,
            "potassium_ppm": profile.potassium_ppm,
            "npk_status": profile.npk_status
        },
        "rationale": profile.rationale
    }


def update_field_agronomic_profile(
    field_name: str,
    soil_type: Optional[str] = None,
    crop: Optional[str] = None,
    growth_stage: Optional[str] = None,
    ph_level: Optional[float] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Updates the agronomic profile (soil_type, crop, growth_stage, ph_level) for a field
    and automatically recalculates and imputes optimal moisture & NPK thresholds.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fields WHERE LOWER(name) = LOWER(?);", (field_name,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"error": f"Field '{field_name}' not found."}

    field = dict(row)
    new_s_type = soil_type or field.get("soil_type", "Loamy")
    new_crop = crop or field.get("crop", "Tomato")
    new_stage = growth_stage or field.get("growth_stage", "Vegetative")
    new_ph = ph_level if ph_level is not None else field.get("ph_level", 6.8)

    profile = AgronomicParameterEngine.impute_field_parameters(
        soil_type=new_s_type,
        crop=new_crop,
        growth_stage=new_stage,
        ph_level=new_ph,
        nitrogen_ppm=field.get("nitrogen_ppm"),
        phosphorus_ppm=field.get("phosphorus_ppm"),
        potassium_ppm=field.get("potassium_ppm")
    )

    cursor.execute(
        """UPDATE fields
           SET soil_type = ?, crop = ?, growth_stage = ?, ph_level = ?,
               wilting_point_pct = ?, field_capacity_pct = ?, optimal_moisture_threshold_pct = ?
           WHERE id = ?;""",
        (
            profile.soil_type, profile.crop, profile.growth_stage, profile.ph_level,
            profile.pwp_pct, profile.fc_pct, profile.optimal_moisture_threshold_pct,
            field["id"]
        )
    )
    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": f"Updated agronomic profile for {field['name']}.",
        "updated_profile": {
            "field_name": field["name"],
            "soil_type": profile.soil_type,
            "crop": profile.crop,
            "growth_stage": profile.growth_stage,
            "ph_level": profile.ph_level,
            "new_optimal_threshold_pct": profile.optimal_moisture_threshold_pct,
            "wilting_point_pct": profile.pwp_pct,
            "field_capacity_pct": profile.fc_pct
        }
    }
