from rest_framework import serializers
from .models import JobData
from ab_scheduler.serializers import DependencySerializer
from ab_scheduler.models import JobStatus


class JobDataSerializer(serializers.HyperlinkedModelSerializer):
    upstream_dep = DependencySerializer(many=True)
    class Meta:
        model = JobData
        fields = ['name', 'obj_type', 'status','upstream_dep','time_stamp']


