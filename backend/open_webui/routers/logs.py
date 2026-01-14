from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List

from open_webui.models.users import Users
from open_webui.utils.auth import get_admin_user
from open_webui.utils.file_logger import (
    get_log_file_info,
    get_log_files,
    read_log_file,
)
from open_webui.config import (
    ENABLE_LOG_TO_FILE,
    LOG_FILE_PATH,
    LOG_FILE_MAX_SIZE,
    LOG_FILE_BACKUP_COUNT,
    LOG_FILE_FORMAT,
    LOG_FILE_DATE_FORMAT,
)

router = APIRouter()


class LogFileConfigForm(BaseModel):
    enable: bool
    path: str
    max_size: str
    backup_count: int
    format: str
    date_format: str


class LogFileInfo(BaseModel):
    enabled: bool
    path: Optional[str] = None
    max_size: Optional[str] = None
    backup_count: Optional[int] = None
    format: Optional[str] = None
    exists: bool
    size: Optional[int] = None
    size_mb: Optional[float] = None
    modified: Optional[float] = None
    error: Optional[str] = None


class LogFileEntry(BaseModel):
    path: str
    name: str
    size: int
    modified: float
    is_main: bool


class LogContent(BaseModel):
    content: str
    total_lines: int
    returned_lines: int
    file_path: str
    file_size: int
    error: Optional[str] = None


@router.get("/config")
async def get_log_file_config(user=Depends(get_admin_user)):
    """Get current log file configuration."""
    return {
        "enable": ENABLE_LOG_TO_FILE.value,
        "path": LOG_FILE_PATH.value,
        "max_size": LOG_FILE_MAX_SIZE.value,
        "backup_count": LOG_FILE_BACKUP_COUNT.value,
        "format": LOG_FILE_FORMAT.value,
        "date_format": LOG_FILE_DATE_FORMAT.value,
    }


@router.post("/config")
async def update_log_file_config(
    form_data: LogFileConfigForm, user=Depends(get_admin_user)
):
    """Update log file configuration."""
    try:
        # Update configuration values
        ENABLE_LOG_TO_FILE.value = form_data.enable
        LOG_FILE_PATH.value = form_data.path
        LOG_FILE_MAX_SIZE.value = form_data.max_size
        LOG_FILE_BACKUP_COUNT.value = form_data.backup_count
        LOG_FILE_FORMAT.value = form_data.format
        LOG_FILE_DATE_FORMAT.value = form_data.date_format

        # Save configuration
        ENABLE_LOG_TO_FILE.save()
        LOG_FILE_PATH.save()
        LOG_FILE_MAX_SIZE.save()
        LOG_FILE_BACKUP_COUNT.save()
        LOG_FILE_FORMAT.save()
        LOG_FILE_DATE_FORMAT.save()

        return {
            "success": True,
            "message": "Log file configuration updated successfully. Restart required for changes to take effect.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update log file configuration: {str(e)}",
        )


@router.get("/info", response_model=LogFileInfo)
async def get_log_info(user=Depends(get_admin_user)):
    """Get information about the current log file."""
    return get_log_file_info()


@router.get("/files", response_model=List[LogFileEntry])
async def get_log_file_list(user=Depends(get_admin_user)):
    """Get list of all log files (main + rotated backups)."""
    return get_log_files()


@router.get("/content")
async def get_log_content(
    lines: int = 100,
    file_index: int = 0,
    user=Depends(get_admin_user),
):
    """
    Read the last N lines from a log file.
    
    Args:
        lines: Number of lines to read from the end (default: 100)
        file_index: Index of log file (0 = main, 1+ = backups)
    """
    result = read_log_file(lines=lines, file_index=file_index)
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "does not exist" in result["error"] else status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )
    
    return result


@router.post("/clear")
async def clear_log_file(user=Depends(get_admin_user)):
    """Clear the main log file."""
    try:
        from pathlib import Path
        
        if not ENABLE_LOG_TO_FILE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File logging is not enabled",
            )
        
        log_path = Path(LOG_FILE_PATH.value)
        if log_path.exists():
            # Clear the file by opening it in write mode
            with open(log_path, 'w') as f:
                pass
            return {"success": True, "message": "Log file cleared successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Log file does not exist",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear log file: {str(e)}",
        )


@router.delete("/files/{file_index}")
async def delete_log_file(file_index: int, user=Depends(get_admin_user)):
    """Delete a specific log file (backup files only, not the main log file)."""
    try:
        from pathlib import Path
        
        if not ENABLE_LOG_TO_FILE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File logging is not enabled",
            )
        
        if file_index == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the main log file. Use clear instead.",
            )
        
        backup_path = Path(f"{LOG_FILE_PATH.value}.{file_index}")
        if backup_path.exists():
            backup_path.unlink()
            return {"success": True, "message": f"Log backup file {file_index} deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Log backup file {file_index} does not exist",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete log file: {str(e)}",
        )
