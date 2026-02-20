import sys
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings
from src.db.models import EntityAttribute, Entity

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_data_quality():
    """
    Scans the database for potential data quality issues, specifically:
    1. Composite values in single-value fields (e.g., "Sand-tempered gray pottery" in Color field).
    2. Missing quotes for extracted values.
    """
    logger.info("Starting Data Quality Check...")
    
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # 1. Define suspicious keywords for cross-contamination check
        # Example: Texture keywords appearing in Color fields
        texture_keywords = ["夹砂", "泥质", "细泥", "Sand-tempered", "Clay", "Fine clay"]
        color_keywords = ["红", "灰", "黑", "褐", "黄", "Red", "Gray", "Black", "Brown", "Yellow"]
        
        # Fetch all attributes
        attributes = db.query(EntityAttribute).all()
        
        issues = []
        
        for attr in attributes:
            val = attr.attribute_value
            if not val:
                continue
                
            # Check 1: Composite Value Detection (Heuristic)
            # If a Color field contains Texture keywords
            if "Color" in attr.attribute_code or "TC" in attr.attribute_code: # Assuming 'TC' is color code prefix
                for kw in texture_keywords:
                    if kw in val:
                        issues.append({
                            "entity_id": str(attr.entity_id),
                            "attribute_id": str(attr.id),
                            "code": attr.attribute_code,
                            "value": val,
                            "issue": f"Potential Composite Value: Texture keyword '{kw}' found in Color field."
                        })
                        break
            
            # If a Texture field contains Color keywords
            if "Texture" in attr.attribute_code or "TX" in attr.attribute_code: # Assuming 'TX' is texture code prefix
                for kw in color_keywords:
                    if kw in val:
                        issues.append({
                            "entity_id": str(attr.entity_id),
                            "attribute_id": str(attr.id),
                            "code": attr.attribute_code,
                            "value": val,
                            "issue": f"Potential Composite Value: Color keyword '{kw}' found in Texture field."
                        })
                        break

            # Check 2: Missing Quotes
            if not attr.original_text or attr.original_text.strip() == "":
                 issues.append({
                    "entity_id": str(attr.entity_id),
                    "attribute_id": str(attr.id),
                    "code": attr.attribute_code,
                    "value": val,
                    "issue": "Missing Quote (Evidence)."
                })

        # Report Results
        if issues:
            logger.warning(f"Found {len(issues)} potential data quality issues.")
            df = pd.DataFrame(issues)
            
            # Print summary to console
            print("\n=== Data Quality Report ===")
            print(df[["code", "value", "issue"]].to_string())
            
            # Save to CSV
            output_file = "data_quality_report.csv"
            df.to_csv(output_file, index=False)
            logger.info(f"Detailed report saved to {output_file}")
        else:
            logger.info("No obvious data quality issues found.")

    except Exception as e:
        logger.error(f"Error during check: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_data_quality()
