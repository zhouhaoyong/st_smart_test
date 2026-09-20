from fastapi import FastAPI

from api.v1.endpoints.test_workbench_routers.merged_ai import router
from services.import_parsers.openapi import _response_metadata
from services.import_parsers.postman import _response_metadata as postman_response_metadata


def test_merged_requirement_ai_router_generates_openapi_schema():
    app = FastAPI()
    app.include_router(router)

    schema = app.openapi()

    assert schema["openapi"].startswith("3.")


def test_response_metadata_keeps_top_level_field_types():
    metadata = _response_metadata({
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "integer"},
                                "message": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    })

    assert metadata["field_types"] == {"code": "int", "message": "string"}


def test_response_metadata_marks_conflicting_field_types_as_unknown():
    metadata = _response_metadata({
        "responses": {
            "200": {"content": {"application/json": {"schema": {
                "type": "object", "properties": {"code": {"type": "integer"}},
            }}}},
            "400": {"content": {"application/json": {"schema": {
                "type": "object", "properties": {"code": {"type": "string"}},
            }}}},
        },
    })

    assert "code" not in metadata["field_types"]
    assert metadata["field_type_conflicts"] == ["code"]


def test_postman_response_metadata_keeps_json_string_type():
    metadata = postman_response_metadata({
        "response": [{"code": 200, "body": '{"code": "200"}'}],
    })

    assert metadata["field_types"] == {"code": "string"}
