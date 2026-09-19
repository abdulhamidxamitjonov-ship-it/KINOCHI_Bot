from aiogram.types import MessageEntity

def serialize_entities(entities):
    return [e.model_dump() for e in (entities or [])]
def deserialize_entities(data):
    return [MessageEntity(**e) for e in (data or [])]
