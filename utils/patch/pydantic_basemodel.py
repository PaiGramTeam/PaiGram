import pydantic

pydantic.BaseModel.model_config["extra"] = "allow"
pydantic.BaseModel.model_config["coerce_numbers_to_str"] = True
pydantic.BaseModel.model_config["arbitrary_types_allowed"] = True
