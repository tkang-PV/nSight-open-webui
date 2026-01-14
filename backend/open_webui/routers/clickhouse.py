from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import clickhouse_connect
import logging
from open_webui.utils.auth import get_admin_user

log = logging.getLogger(__name__)

router = APIRouter()

# ClickHouse connection configuration
CLICKHOUSE_HOST = "172.31.5.136"  # Configure as needed
CLICKHOUSE_PORT = 8123
CLICKHOUSE_USERNAME = "RO_User"  # Configure as needed
CLICKHOUSE_PASSWORD = "RO_User"  # Configure as needed

class CustomerResponse(BaseModel):
    customers: List[str]

def get_clickhouse_client():
    """Get ClickHouse client connection"""
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            username=CLICKHOUSE_USERNAME,
            password=CLICKHOUSE_PASSWORD
        )
        return client
    except Exception as e:
        log.error(f"Failed to connect to ClickHouse: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to ClickHouse")

@router.get("/customers/{region}", response_model=CustomerResponse)
async def get_customers_by_region(region: str, user=Depends(get_admin_user)):
    """
    Get customers by region from ClickHouse database
    """
    try:
        client = get_clickhouse_client()
        
        # Execute the query with parameterized input to prevent SQL injection
        query = "SELECT CustomerAdWebsite FROM nSight_all.Lookup_CustomerAdWebsite WHERE Location = %(region)s"
        
        result = client.query(query, parameters={"region": region})
        
        # Extract customer names from the result
        customers = [row[0] for row in result.result_rows if row[0]]
        
        return CustomerResponse(customers=customers)
        
    except Exception as e:
        log.error(f"Error querying ClickHouse: {e}")
        raise HTTPException(status_code=500, detail=f"Error querying database: {str(e)}")

@router.get("/regions")
async def get_regions(user=Depends(get_admin_user)):
    """
    Get available regions (static list)
    """
    regions = ["eu", "frankfurt", "oregon", "sydney", "us"]
    return {"regions": regions}
