"""Multi-brand/GEO selection for Auto Pilot; each transfer group stays singular."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.domain_transfer_policy import geo_key
from app.mass_action_scope import brand_key


def country_key(value):
    code = geo_key(value)
    return 'CZ' if code == 'CS' else code


class PilotScopeError(ValueError):
    """A requested exclusion would remove a whole authorized GEO."""


class PilotSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scope_mode: Literal['include', 'exclude'] = 'include'
    brands: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(default_factory=list, max_length=5)
    geos: list[Annotated[str, Field(min_length=2, max_length=16)]] = Field(default_factory=list, max_length=250)

    @field_validator('brands')
    @classmethod
    def valid_brands(cls, values):
        result = {}
        for value in values:
            if not brand_key(value):
                raise ValueError('Укажите название бренда.')
            result.setdefault(brand_key(value), value.strip())
        return list(result.values())

    @field_validator('geos')
    @classmethod
    def valid_geos(cls, values):
        result = []
        for value in values:
            code = country_key(value)
            if len(code) != 2 or not code.isascii() or not code.isalpha():
                raise ValueError('Укажите двухбуквенный код GEO.')
            if code not in result:
                result.append(code)
        return result

    @model_validator(mode='after')
    def explicit_exclusions(self):
        if self.scope_mode == 'exclude' and (not self.brands or not self.geos):
            raise ValueError('Для исключения выберите хотя бы один бренд и одно GEO. Исключение всего GEO не допускается.')
        return self

    def includes(self, brand, geo):
        matching = (not self.brands or brand_key(brand) in {brand_key(value) for value in self.brands}) and (not self.geos or country_key(geo) in self.geos)
        return not matching if self.scope_mode == 'exclude' else matching


def selection(saved=None, *, brand='', geo='', brands=None, geos=None, scope_mode='include'):
    if saved is not None:
        scope_mode = saved.get('scope_mode', 'include')
        brand, geo = saved.get('brand', ''), saved.get('geo', '')
        brands, geos = saved.get('brands'), saved.get('geos')
    return PilotSelection(scope_mode=scope_mode, brands=brands if brands is not None else [brand] if brand else [],
                          geos=geos if geos is not None else [geo] if geo else [])
