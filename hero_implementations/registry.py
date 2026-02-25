"""Registry for hero implementations."""

from hero_implementations.default import DefaultHeroImplementation
from hero_implementations.helpers import normalize_key
from hero_implementations.phantom_assassin import PhantomAssassinImplementation


class HeroImplementationRegistry:
    """Lookup and registration for hero logic classes."""

    _registry = {}
    _default_impl = DefaultHeroImplementation()

    @classmethod
    def register(cls, impl_cls):
        key = normalize_key(impl_cls.hero_key())
        cls._registry[key] = impl_cls
        return impl_cls

    @classmethod
    def get_implementation(cls, hero_name):
        key = normalize_key(hero_name)
        impl_cls = cls._registry.get(key)
        if impl_cls is None:
            return cls._default_impl
        return impl_cls()


HeroImplementationRegistry.register(PhantomAssassinImplementation)
