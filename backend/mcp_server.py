from mcp.server.fastmcp import FastMCP
import json

mcp = FastMCP("Lab Analyzer")

REFERENCE_RANGES = {
    "Hemoglobin": {"min": 12.0, "max": 15.0, "unit": "g/dL"},
    "Glucose": {"min": 70.0, "max": 99.0, "unit": "mg/dL"},
    "Glukoz": {"min": 70.0, "max": 99.0, "unit": "mg/dL"}, # Turkish
    "Lökosit": {"min": 4.5, "max": 11.0, "unit": "10^3/uL"}, # Turkish WBC
    "Trombosit": {"min": 150.0, "max": 450.0, "unit": "10^3/uL"}, # Turkish Platelets
    "Creatinine": {"min": 0.6, "max": 1.2, "unit": "mg/dL"},
    "Ferritin": {"min": 15.0, "max": 150.0, "unit": "ug/L"},
    "TSH": {"min": 0.4, "max": 4.0, "unit": "mIU/L"},
    "Eritrosit": {"min": 3.8, "max": 5.2, "unit": "10^6/uL"}, # Turkish RBC
}

@mcp.tool()
def reference_range_lookup(test_name: str) -> str:
    """Lookup the reference range for a given clinical laboratory test.
    Args:
        test_name: The name of the test (e.g. Hemoglobin, Glucose, Ferritin)
    Returns:
        JSON string containing min, max, and unit, or an error if not found.
    """
    for key, val in REFERENCE_RANGES.items():
        if key.lower() in test_name.lower():
            return json.dumps({"test_name": key, "min": val["min"], "max": val["max"], "unit": val["unit"]})
    
    return json.dumps({"error": f"Reference range for {test_name} not found in local database."})

if __name__ == "__main__":
    try:
        mcp.run()
    except Exception as e:
        import traceback
        with open("mcp_server_error.log", "w") as f:
            f.write(traceback.format_exc())
            f.write("\n")
            f.write(str(e))
        raise
