from typing import Optional
import io
import base64
import json
import asyncio
import logging
import traceback

from open_webui.models.groups import Groups
from open_webui.models.models import (
    ModelForm,
    ModelModel,
    ModelResponse,
    ModelListResponse,
    ModelAccessListResponse,
    ModelAccessResponse,
    Models,
)

from pydantic import BaseModel
from open_webui.constants import ERROR_MESSAGES
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
    Response,
)
from fastapi.responses import FileResponse, StreamingResponse


from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.access_control import has_access, has_permission
from open_webui.config import BYPASS_ADMIN_ACCESS_CONTROL, STATIC_DIR, save_config, CONFIG_DATA
from open_webui.internal.db import get_session
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def _update_strands_config_from_model(form_data: ModelForm):
    """Extract and save Strands configuration from model metadata to CONFIG_DATA"""
    try:
        log.info(f"[MODELS HANDLER] ===== _update_strands_config_from_model START =====")
        log.info(f"[MODELS HANDLER] Model ID: {form_data.id}")
        log.info(f"[MODELS HANDLER] Model name: {form_data.name}")
        log.info(f"[MODELS HANDLER] form_data type: {type(form_data)}")
        log.info(f"[MODELS HANDLER] form_data.meta type: {type(form_data.meta)}")
        log.info(f"[MODELS HANDLER] form_data.meta is dict: {isinstance(form_data.meta, dict)}")
        
        # Convert Pydantic model to dict if needed
        meta_dict = None
        if form_data.meta:
            if isinstance(form_data.meta, dict):
                meta_dict = form_data.meta
                log.info(f"[MODELS HANDLER] form_data.meta is already a dict")
            elif hasattr(form_data.meta, 'model_dump'):
                meta_dict = form_data.meta.model_dump()
                log.info(f"[MODELS HANDLER] Converted Pydantic model to dict using model_dump()")
            elif hasattr(form_data.meta, 'dict'):
                meta_dict = form_data.meta.dict()
                log.info(f"[MODELS HANDLER] Converted Pydantic model to dict using dict()")
            else:
                log.warning(f"[MODELS HANDLER] form_data.meta has unknown type, attempting str conversion")
                log.debug(f"[MODELS HANDLER] form_data.meta dir(): {dir(form_data.meta)}")
            
            if meta_dict:
                log.info(f"[MODELS HANDLER] meta_dict keys: {list(meta_dict.keys())}")
                log.debug(f"[MODELS HANDLER] meta_dict full content: {meta_dict}")
            else:
                log.warning(f"[MODELS HANDLER] Failed to convert meta to dict")
        else:
            log.warning(f"[MODELS HANDLER] form_data.meta is None or empty")
        
        # Check if this is a Strands model with strands config in metadata
        if meta_dict:
            log.info(f"[MODELS HANDLER] meta_dict is valid")
            
            if 'strands' in meta_dict:
                strands_config = meta_dict['strands']
                log.info(f"[MODELS HANDLER] ✓ Found 'strands' key in metadata")
                log.info(f"[MODELS HANDLER] strands_config type: {type(strands_config)}")
                log.info(f"[MODELS HANDLER] strands_config: {strands_config}")
                
                # Ensure CONFIG_DATA has strands key
                if 'strands' not in CONFIG_DATA:
                    log.warning(f"[MODELS HANDLER] 'strands' key not in CONFIG_DATA, creating it")
                    CONFIG_DATA['strands'] = {}
                else:
                    log.info(f"[MODELS HANDLER] 'strands' key already exists in CONFIG_DATA")
                
                log.info(f"[MODELS HANDLER] CONFIG_DATA['strands'] before update: {CONFIG_DATA['strands']}")
                
                # Update CONFIG_DATA with the provided strands config
                updated_fields = []
                
                if 'AWS_PROFILE' in strands_config:
                    old_value = CONFIG_DATA['strands'].get('AWS_PROFILE')
                    new_value = strands_config['AWS_PROFILE']
                    CONFIG_DATA['strands']['AWS_PROFILE'] = new_value
                    updated_fields.append('AWS_PROFILE')
                    log.info(f"[MODELS HANDLER] AWS_PROFILE: {old_value} -> {new_value}")
                
                if 'AWS_REGION' in strands_config:
                    old_value = CONFIG_DATA['strands'].get('AWS_REGION')
                    new_value = strands_config['AWS_REGION']
                    CONFIG_DATA['strands']['AWS_REGION'] = new_value
                    updated_fields.append('AWS_REGION')
                    log.info(f"[MODELS HANDLER] AWS_REGION: {old_value} -> {new_value}")
                
                if 'MODEL_ID' in strands_config:
                    old_value = CONFIG_DATA['strands'].get('MODEL_ID')
                    new_value = strands_config['MODEL_ID']
                    CONFIG_DATA['strands']['MODEL_ID'] = new_value
                    updated_fields.append('MODEL_ID')
                    log.info(f"[MODELS HANDLER] MODEL_ID: {old_value} -> {new_value}")
                
                if 'CLICKHOUSE_MCP_BASE_URL' in strands_config:
                    old_value = CONFIG_DATA['strands'].get('CLICKHOUSE_MCP_BASE_URL')
                    new_value = strands_config['CLICKHOUSE_MCP_BASE_URL']
                    CONFIG_DATA['strands']['CLICKHOUSE_MCP_BASE_URL'] = new_value
                    updated_fields.append('CLICKHOUSE_MCP_BASE_URL')
                    log.info(f"[MODELS HANDLER] CLICKHOUSE_MCP_BASE_URL: {old_value} -> {new_value}")
                
                log.info(f"[MODELS HANDLER] CONFIG_DATA['strands'] after updates: {CONFIG_DATA['strands']}")
                log.info(f"[MODELS HANDLER] Updated fields count: {len(updated_fields)}")
                log.info(f"[MODELS HANDLER] Updated fields: {updated_fields}")
                
                if updated_fields:
                    log.info(f"[MODELS HANDLER] Calling save_config() with updated CONFIG_DATA")
                    log.debug(f"[MODELS HANDLER] Full CONFIG_DATA being saved: {CONFIG_DATA}")
                    
                    success = save_config(CONFIG_DATA)
                    log.info(f"[MODELS HANDLER] save_config() returned: {success} (type: {type(success)})")
                    
                    if success:
                        log.info(f"[MODELS HANDLER] ✓ Strands configuration persisted successfully to database")
                        log.info(f"[MODELS HANDLER] Verifying CONFIG_DATA after save_config(): {CONFIG_DATA.get('strands', {})}")
                    else:
                        log.warning(f"[MODELS HANDLER] ⚠️ save_config returned False - config may not have been saved")
                else:
                    log.warning(f"[MODELS HANDLER] ⚠️ No fields were updated from strands config")
            else:
                log.warning(f"[MODELS HANDLER] 'strands' key NOT found in meta_dict")
                log.info(f"[MODELS HANDLER] Available keys in meta_dict: {list(meta_dict.keys())}")
        else:
            log.warning(f"[MODELS HANDLER] meta_dict is not valid or is None")
        
        log.info(f"[MODELS HANDLER] ===== _update_strands_config_from_model END =====")
    except Exception as e:
        log.error(f"[MODELS HANDLER] ✗ Error updating Strands config: {e}")
        log.error(f"[MODELS HANDLER] Exception type: {type(e).__name__}")
        log.error(f"[MODELS HANDLER] Traceback: {traceback.format_exc()}")

router = APIRouter()


def is_valid_model_id(model_id: str) -> bool:
    return model_id and len(model_id) <= 256


###########################
# GetModels
###########################


PAGE_ITEM_COUNT = 30


@router.get(
    "/list", response_model=ModelAccessListResponse
)  # do NOT use "/" as path, conflicts with main.py
async def get_models(
    query: Optional[str] = None,
    view_option: Optional[str] = None,
    tag: Optional[str] = None,
    order_by: Optional[str] = None,
    direction: Optional[str] = None,
    page: Optional[int] = 1,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):

    limit = PAGE_ITEM_COUNT

    page = max(1, page)
    skip = (page - 1) * limit

    filter = {}
    if query:
        filter["query"] = query
    if view_option:
        filter["view_option"] = view_option
    if tag:
        filter["tag"] = tag
    if order_by:
        filter["order_by"] = order_by
    if direction:
        filter["direction"] = direction

    if not user.role == "admin" or not BYPASS_ADMIN_ACCESS_CONTROL:
        groups = Groups.get_groups_by_member_id(user.id, db=db)
        if groups:
            filter["group_ids"] = [group.id for group in groups]

        filter["user_id"] = user.id

    result = Models.search_models(user.id, filter=filter, skip=skip, limit=limit, db=db)
    return ModelAccessListResponse(
        items=[
            ModelAccessResponse(
                **model.model_dump(),
                write_access=(
                    (user.role == "admin" and BYPASS_ADMIN_ACCESS_CONTROL)
                    or user.id == model.user_id
                    or has_access(user.id, "write", model.access_control, db=db)
                ),
            )
            for model in result.items
        ],
        total=result.total,
    )


###########################
# GetBaseModels
###########################


@router.get("/base", response_model=list[ModelResponse])
async def get_base_models(
    user=Depends(get_admin_user), db: Session = Depends(get_session)
):
    return Models.get_base_models(db=db)


###########################
# GetModelTags
###########################


@router.get("/tags", response_model=list[str])
async def get_model_tags(
    user=Depends(get_verified_user), db: Session = Depends(get_session)
):
    if user.role == "admin" and BYPASS_ADMIN_ACCESS_CONTROL:
        models = Models.get_models(db=db)
    else:
        models = Models.get_models_by_user_id(user.id, db=db)

    tags_set = set()
    for model in models:
        if model.meta:
            meta = model.meta.model_dump()
            for tag in meta.get("tags", []):
                tags_set.add((tag.get("name")))

    tags = [tag for tag in tags_set]
    tags.sort()
    return tags


############################
# CreateNewModel
############################


@router.post("/create", response_model=Optional[ModelModel])
async def create_new_model(
    request: Request,
    form_data: ModelForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    log.info(f"[MODELS CREATE] ===== POST /create START =====")
    log.info(f"[MODELS CREATE] Received model creation request")
    log.info(f"[MODELS CREATE] Model ID: {form_data.id}")
    log.info(f"[MODELS CREATE] Model name: {form_data.name}")
    log.info(f"[MODELS CREATE] form_data type: {type(form_data)}")
    log.debug(f"[MODELS CREATE] Full form_data: {form_data}")
    log.info(f"[MODELS CREATE] form_data.meta type: {type(form_data.meta)}")
    if form_data.meta:
        log.info(f"[MODELS CREATE] form_data.meta keys: {list(form_data.meta.keys()) if isinstance(form_data.meta, dict) else 'NOT_A_DICT'}")
        if isinstance(form_data.meta, dict) and 'strands' in form_data.meta:
            log.info(f"[MODELS CREATE] ✓ Strands config found in request: {form_data.meta['strands']}")
        else:
            log.warning(f"[MODELS CREATE] ⚠️ Strands config NOT found in request meta")
    else:
        log.warning(f"[MODELS CREATE] form_data.meta is None or empty")
    
    if user.role != "admin" and not has_permission(
        user.id, "workspace.models", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    model = Models.get_model_by_id(form_data.id, db=db)
    if model:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.MODEL_ID_TAKEN,
        )

    if not is_valid_model_id(form_data.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.MODEL_ID_TOO_LONG,
        )

    else:
        # Extract and save Strands configuration if present
        log.info(f"[MODELS CREATE] Calling _update_strands_config_from_model()")
        _update_strands_config_from_model(form_data)
        log.info(f"[MODELS CREATE] Returned from _update_strands_config_from_model()")
        
        log.info(f"[MODELS CREATE] Calling Models.insert_new_model()")
        model = Models.insert_new_model(form_data, user.id, db=db)
        if model:
            log.info(f"[MODELS CREATE] ✓ Model created successfully: {form_data.id}")
            log.info(f"[MODELS CREATE] ===== POST /create END =====")
            return model
        else:
            log.error(f"[MODELS CREATE] ✗ Failed to create model")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.DEFAULT(),
            )


############################
# ExportModels
############################


@router.get("/export", response_model=list[ModelModel])
async def export_models(
    request: Request,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    if user.role != "admin" and not has_permission(
        user.id,
        "workspace.models_export",
        request.app.state.config.USER_PERMISSIONS,
        db=db,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    if user.role == "admin" and BYPASS_ADMIN_ACCESS_CONTROL:
        return Models.get_models(db=db)
    else:
        return Models.get_models_by_user_id(user.id, db=db)


############################
# ImportModels
############################


class ModelsImportForm(BaseModel):
    models: list[dict]


@router.post("/import", response_model=bool)
async def import_models(
    request: Request,
    user=Depends(get_verified_user),
    form_data: ModelsImportForm = (...),
    db: Session = Depends(get_session),
):
    if user.role != "admin" and not has_permission(
        user.id,
        "workspace.models_import",
        request.app.state.config.USER_PERMISSIONS,
        db=db,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )
    try:
        data = form_data.models
        if isinstance(data, list):
            for model_data in data:
                # Here, you can add logic to validate model_data if needed
                model_id = model_data.get("id")

                if model_id and is_valid_model_id(model_id):
                    existing_model = Models.get_model_by_id(model_id, db=db)
                    if existing_model:
                        # Update existing model
                        model_data["meta"] = model_data.get("meta", {})
                        model_data["params"] = model_data.get("params", {})

                        updated_model = ModelForm(
                            **{**existing_model.model_dump(), **model_data}
                        )
                        Models.update_model_by_id(model_id, updated_model, db=db)
                    else:
                        # Insert new model
                        model_data["meta"] = model_data.get("meta", {})
                        model_data["params"] = model_data.get("params", {})
                        new_model = ModelForm(**model_data)
                        Models.insert_new_model(
                            user_id=user.id, form_data=new_model, db=db
                        )
            return True
        else:
            raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=500, detail=str(e))


############################
# SyncModels
############################


class SyncModelsForm(BaseModel):
    models: list[ModelModel] = []


@router.post("/sync", response_model=list[ModelModel])
async def sync_models(
    request: Request,
    form_data: SyncModelsForm,
    user=Depends(get_admin_user),
    db: Session = Depends(get_session),
):
    return Models.sync_models(user.id, form_data.models, db=db)


###########################
# GetModelById
###########################


class ModelIdForm(BaseModel):
    id: str


# Note: We're not using the typical url path param here, but instead using a query parameter to allow '/' in the id
@router.get("/model", response_model=Optional[ModelAccessResponse])
async def get_model_by_id(
    id: str, user=Depends(get_verified_user), db: Session = Depends(get_session)
):
    model = Models.get_model_by_id(id, db=db)
    if model:
        if (
            (user.role == "admin" and BYPASS_ADMIN_ACCESS_CONTROL)
            or model.user_id == user.id
            or has_access(user.id, "read", model.access_control, db=db)
        ):
            return ModelAccessResponse(
                **model.model_dump(),
                write_access=(
                    (user.role == "admin" and BYPASS_ADMIN_ACCESS_CONTROL)
                    or user.id == model.user_id
                    or has_access(user.id, "write", model.access_control, db=db)
                ),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


###########################
# GetModelById
###########################


@router.get("/model/profile/image")
def get_model_profile_image(
    id: str, user=Depends(get_verified_user), db: Session = Depends(get_session)
):
    model = Models.get_model_by_id(id, db=db)

    if model:
        etag = f'"{model.updated_at}"' if model.updated_at else None

        if model.meta.profile_image_url:
            if model.meta.profile_image_url.startswith("http"):
                return Response(
                    status_code=status.HTTP_302_FOUND,
                    headers={"Location": model.meta.profile_image_url},
                )
            elif model.meta.profile_image_url.startswith("data:image"):
                try:
                    header, base64_data = model.meta.profile_image_url.split(",", 1)
                    image_data = base64.b64decode(base64_data)
                    image_buffer = io.BytesIO(image_data)
                    media_type = header.split(";")[0].lstrip("data:")

                    headers = {"Content-Disposition": "inline"}
                    if etag:
                        headers["ETag"] = etag

                    return StreamingResponse(
                        image_buffer,
                        media_type=media_type,
                        headers=headers,
                    )
                except Exception as e:
                    pass

        return FileResponse(f"{STATIC_DIR}/favicon.png")
    else:
        return FileResponse(f"{STATIC_DIR}/favicon.png")


############################
# ToggleModelById
############################


@router.post("/model/toggle", response_model=Optional[ModelResponse])
async def toggle_model_by_id(
    id: str, user=Depends(get_verified_user), db: Session = Depends(get_session)
):
    model = Models.get_model_by_id(id, db=db)
    if model:
        if (
            user.role == "admin"
            or model.user_id == user.id
            or has_access(user.id, "write", model.access_control, db=db)
        ):
            model = Models.toggle_model_by_id(id, db=db)

            if model:
                return model
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.DEFAULT("Error updating function"),
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.UNAUTHORIZED,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# UpdateModelById
############################


@router.post("/model/update", response_model=Optional[ModelModel])
async def update_model_by_id(
    form_data: ModelForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    log.info(f"[MODELS UPDATE] ===== POST /model/update START =====")
    log.info(f"[MODELS UPDATE] Received model update request")
    log.info(f"[MODELS UPDATE] Model ID: {form_data.id}")
    log.info(f"[MODELS UPDATE] Model name: {form_data.name}")
    log.info(f"[MODELS UPDATE] form_data type: {type(form_data)}")
    log.debug(f"[MODELS UPDATE] Full form_data: {form_data}")
    log.info(f"[MODELS UPDATE] form_data.meta type: {type(form_data.meta)}")
    if form_data.meta:
        log.info(f"[MODELS UPDATE] form_data.meta keys: {list(form_data.meta.keys()) if isinstance(form_data.meta, dict) else 'NOT_A_DICT'}")
        if isinstance(form_data.meta, dict) and 'strands' in form_data.meta:
            log.info(f"[MODELS UPDATE] ✓ Strands config found in request: {form_data.meta['strands']}")
        else:
            log.warning(f"[MODELS UPDATE] ⚠️ Strands config NOT found in request meta")
    else:
        log.warning(f"[MODELS UPDATE] form_data.meta is None or empty")
    
    model = Models.get_model_by_id(form_data.id, db=db)
    if not model:
        log.error(f"[MODELS UPDATE] ✗ Model not found: {form_data.id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        model.user_id != user.id
        and not has_access(user.id, "write", model.access_control, db=db)
        and user.role != "admin"
    ):
        log.error(f"[MODELS UPDATE] ✗ Access denied for user {user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    # Extract and save Strands configuration if present
    log.info(f"[MODELS UPDATE] Calling _update_strands_config_from_model()")
    _update_strands_config_from_model(form_data)
    log.info(f"[MODELS UPDATE] Returned from _update_strands_config_from_model()")

    log.info(f"[MODELS UPDATE] Calling Models.update_model_by_id()")
    model = Models.update_model_by_id(
        form_data.id, ModelForm(**form_data.model_dump()), db=db
    )
    log.info(f"[MODELS UPDATE] ✓ Model updated successfully: {form_data.id}")
    log.info(f"[MODELS UPDATE] ===== POST /model/update END =====")
    return model


############################
# DeleteModelById
############################


@router.post("/model/delete", response_model=bool)
async def delete_model_by_id(
    form_data: ModelIdForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    model = Models.get_model_by_id(form_data.id, db=db)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        user.role != "admin"
        and model.user_id != user.id
        and not has_access(user.id, "write", model.access_control, db=db)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    result = Models.delete_model_by_id(form_data.id, db=db)
    return result


@router.delete("/delete/all", response_model=bool)
async def delete_all_models(
    user=Depends(get_admin_user), db: Session = Depends(get_session)
):
    result = Models.delete_all_models(db=db)
    return result
