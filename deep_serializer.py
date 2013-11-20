from django.db import models
from django.core.serializers.python import Serializer
from django.utils import six
import pdb

'''
    Follows foreign key relationships in both directions. This inevitably creates circular references. This is handled in two ways:
        1) There's a 'max_depth' parameter (defaults to 3) which controls how many levels of nesting deep the serializer will go
        2) There's a "parents" list which is maintained (and copied and branched recursively). If objects whose class appears in the parents list won't be serialized. This is fails in the case of multi-table inheritence when there's
        a foreign key in the parent table
'''

class DeepSerializer(Serializer):
    
    def end_object(self, obj):
        if self.nesting_depth < self.max_depth:
            for related in obj._meta.get_all_related_objects():
                relatedSerializer = DeepSerializer()
                relatedSet = False
                try:
                    
                    parentsArg = list(self.parents)
                    parentsArg.append(obj.__class__)
                    relatedSet = getattr(obj, related.var_name + "_set")
                    if len(relatedSet.all()) > 0 and relatedSet.all()[0].__class__ not in parentsArg:
                        self._current[related.model._meta.verbose_name_plural.decode()] = relatedSerializer.serialize(relatedSet.all(),max_depth=self.max_depth, nesting_depth=self.nesting_depth + 1,  parents=parentsArg)        
                except:
                    pass
        
        self.objects.append(self._current)
        self._current = None
        
    def serialize(self, queryset, **options):
        
        self.options = options
        
        self.stream = options.pop("stream", six.StringIO())
        self.selected_fields = options.pop("fields", None)
        self.use_natural_keys = options.pop("use_natural_keys", False)
        self.ancestor_models = options.pop("ancestor_models", [])
        self.nesting_depth = options.pop("nesting_depth", 1) 
        self.max_depth = options.pop("max_depth", 3)
        self.parents = options.pop("parents", [])
        
        self.start_serialization()
        self.first = True
        for obj in queryset:
            self.start_object(obj)
            # Use the concrete parent class' _meta instead of the object's _meta
            # This is to avoid local_fields problems for proxy models. Refs #17717.
            concrete_model = obj._meta.concrete_model
            
            for field in concrete_model._meta.fields:
                if field.serialize:
                    if field.rel is None:
                        if self.selected_fields is None or field.attname in self.selected_fields:
                            self.handle_field(obj, field)
                    else:
                        if self.selected_fields is None or field.attname[:-3] in self.selected_fields:
                            self.handle_fk_field(obj, field)
            for field in concrete_model._meta.many_to_many:
                if field.serialize:
                    if self.selected_fields is None or field.attname in self.selected_fields:
                        self.handle_m2m_field(obj, field)
            self.end_object(obj)
            if self.first:
                self.first = False
        self.end_serialization()
        
        return self.getvalue()
        
    def handle_fk_field(self, obj, field): 
        if self.nesting_depth < self.max_depth:
            parentsArg = list(self.parents)
            parentsArg.append(obj.__class__)
            if getattr(obj, field.name).__class__ not in parentsArg:
                self._current[field.name] = DeepSerializer().serialize([getattr(obj, field.name)], max_depth=self.max_depth, nesting_depth=self.nesting_depth + 1, parents=parentsArg)[0]

				
