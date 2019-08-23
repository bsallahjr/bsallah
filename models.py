from __future__ import unicode_literals

from django.db import models
from ab_shared.models import NumericSetField
from ab_scheduler.models import Dependency
from abmetrics_django.models import Metric, MetricGroup
RUNNING = 'Running'
COMPLETE = 'Complete'
WAITING = 'Waiting for Dependencies'
FAILED = 'Failed'
STATUS_CHOICES = ((RUNNING, RUNNING), (COMPLETE, COMPLETE), (WAITING, WAITING), (FAILED, FAILED))
LISTENER_ACTIVITY = 'Listener Activity'
BASELINE = 'Baseline'
STATS_AND_TESTS = 'Stats and Tests'
PART_OF_PIPELINE_CHOICES = ((LISTENER_ACTIVITY, LISTENER_ACTIVITY), (BASELINE, BASELINE),
                            (STATS_AND_TESTS, STATS_AND_TESTS))
from ab_scheduler.constants import JOB_TYPE_CHOICES
JOB = 'Job'

LOCATION_RUNNING_CHOICES = (('AWS',), ('Airflow',), ('GCP',))

# Create your models here.


class JobData(models.Model):
    obj_id = models.IntegerField(null=True)
    name           = models.CharField(max_length=100, null=True)
    obj_type = models.CharField(max_length=100, choices=JOB_TYPE_CHOICES,null=True)
    # status will be captured by the UI
    status         = models.CharField(max_length=100, choices=STATUS_CHOICES,null=True)
    upstream_dep   = models.ManyToManyField(Dependency, related_name='downstream')  # dependencies table in ab-metrics_django.models
    # LsTable has a dependencies field, what is this for
    time_stamp = models.DateTimeField(null=True, auto_now=True)
    # date will be tagged when pulled
    def __str__(self):
        return self.name



