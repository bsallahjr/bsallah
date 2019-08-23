from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse, JsonResponse

import django
from ab_util.api_util import construct_json_api_response

django.setup()
from rest_framework import viewsets
from rest_framework.response import Response
import json
from rest_framework.status import *
from rest_framework.exceptions import NotFound
from rest_framework.decorators import api_view
from ab_experiment_att.models import ExperimentOwner, ExperimentWatcher
from ab_experiment_setup.models import EFExperimentGroup
from abmetrics_django.models import *
from ab_experiment_core.models import Experiment
import itertools
from ab_scheduler.analytics_job_util import get_analytics_job_status_by_job_name
from ab_scheduler.models import *
from ab_scheduler.constants import METRIC_VARIABLE, METRIC_GROUP, METRIC, EXPERIMENT, \
    LISTENER_SUMMARY, JOB, HIVE_LISTENER_SUMMARY
from zelda.models import JobData
from zelda.serializers import JobDataSerializer
from django.shortcuts import get_object_or_404, render
all_jobs = list(set([m.job for m in JobStatus.objects.all()]))


dependencies = {
u'CrossSegmentCount': ['Baseline'],
u'Baseline': ['BaselineInit', 'ExposureRollup', 'ABListenerComparisonArmUpdateJob', 'ABWhitelist', 'ABComparisonExposure'],
u'BaselineInit': ['ABListenerComparisonArmInitialJob', 'ABMetadataStartDateJob',
                 'ab_ls_subscription_status', 'ab_ls_retention_segment'],
u'ExposureRollup': ['ABMetadataStartDateJob', 'ab_ls_mobile_users_on_podcast_app_versions',
                   'ab_ls_premium_and_premium_access_listeners', 'ab_ls_premium_and_premium_access_listeners',
                   'ab_ls_search_users'],
u'BaselineDenormalizer': ['Baseline'],
u'AnalyticsJob': []
}



def uniques(lst):
    return list(set(lst))


def get_user_data(username):

    exp_group_ids = [m.expt_group_id for m in ExptGroupOwner.objects.filter(owner=username).all()]
    exp_to_cat = list(itertools.chain.from_iterable(
        [m for m in [ExptToCategory.objects.filter(expt_group_id=qry).all() for qry in exp_group_ids]]))
    categories = [m.category for m in exp_to_cat]
    cat_to_metric_group = list(itertools.chain.from_iterable(
        [m for m in [MetricGroupToCategory.objects.filter(category=qry).all() for qry in categories]]))
    subbed_metric_groups = uniques([m.metric_group_id for m in cat_to_metric_group])
    owned_metrics = [m.id for m in MetricGroup.objects.filter(owner=username)]
    core_metrics = [m.metric_groups.all() for m in Category.objects.filter(code='core')]
    core_metrics = [m.id for m in core_metrics[0]]
    owned_and_core_metrics = uniques(owned_metrics + core_metrics)
    watched_expts = uniques([m.experiment_att.experiment.experiment_id for m in ExperimentWatcher.objects.filter(user=username)])
    owned_expts = uniques(exp_group_ids +
                          [m.experiment_att.experiment.experiment_id for m in ExperimentOwner.objects.filter(user=username)])

    return {'username': username, 'subbed_metric_groups': subbed_metric_groups,
            'owned_and_core_metrics': owned_and_core_metrics, 'owned_expts': owned_expts,
            'watched_expts': watched_expts}


def get_job_status(job_name, job_type, day):
    status = None
    analytics_jobs = [m.dependencies.all() for m in LsTable.objects.all()]
    if job_name in analytics_jobs:
        status = get_analytics_job_status_by_job_name(job_name, day)
        return Response({'status': status})
    else:
        if day is None:
            status = 'INVALID_INPUT: Please specify a date.'
        if job_name is None:
            status = 'INVALID_INPUT: Job name is missing.'
        if job_type is None:
            status = 'INVALID_INPUT: Job type is missing.'

        if not status:
            # find the job of interest
            result = JobStatus.objects.filter(
                type=job_type, job=job_name, start_day__gte=day, end_day__lte=day)

            if not result:
                status = 'No Data'
            else:
                status = result[0].status

        return status


def fill_shell(metric, day):
    """
    Creates the JSON using the shell dict that will be converted
    to the tree by D3
    status variable -> status
    technos -> node type
    :param metric:
    :param day:
    :return:
    """
    shell = {'name': '', 'technos': [METRIC], 'status': 'No Data',
             'children': [{
                 'name': '', 'technos': [METRIC_GROUP],'status': '',
                 'children': [{
                     'name': '', 'technos': [METRIC_VARIABLE],'status': '',
                     'children': []
                 }]
             }]}

    shell['name'] = metric.name
    mg_dep = metric.upstream_dep.all()[0]
    mg = JobData.objects.get(name=mg_dep.dependency, obj_type=METRIC_GROUP)
    shell['children'][0]['name'] = mg.name
    shell['children'][0]['status'] = get_job_status(mg.name, METRIC_GROUP, day)
    shell['children'][0]['children'][0]['name'] = mg.name
    shell['children'][0]['children'][0]['status'] = get_job_status(mg.name, METRIC_VARIABLE, day)
    mv = JobData.objects.get(name=mg.name, obj_type=METRIC_VARIABLE)
    ls_dep = []
    up_of_ls = []
    up_of_ls_ = []
    for dep in mv.upstream_dep.all():
        ls_shell = {'name': '', 'technos': [LISTENER_SUMMARY],'status': '', 'children': []}
        ls_shell['name'] = dep.dependency
        ls_shell['status'] = get_job_status(dep.dependency,LISTENER_SUMMARY, day)
        ls = LsTable.objects.get(name=dep.dependency)
        up_of_ls = ls.dependencies.all()
        for x in up_of_ls:
            third_party = {'name': '', 'technos': '', 'status': '',}
            third_party['name'] = x.dependency
            up_of_ls_.append(third_party)
        ls_shell['children'] = up_of_ls_
        ls_dep.append(ls_shell)
    shell['children'][0]['children'][0]['children'] = ls_dep

    return shell


if __name__ == '__main__':
    m = JobData.objects.filter(obj_type=METRIC)[4]
    print fill_shell(m)


@api_view(['GET'])
def get_users_data(request):
    """
    Filters JobData object and renders data in a tree visualization
    :return:
    """
    username = request.user.username
    user_data = get_user_data(username)
    try:
        metric_names = [MetricGroup.objects.get(id=id).metrics.all() for id in user_data["subbed_metric_groups"]+user_data["owned_and_core_metrics"]]
    except MetricGroup.DoesNotExist:
        logger.error('Could not find MetricGroup')
    print metric_names
    metric_names = list(itertools.chain.from_iterable(metric_names))
    new_date = request.GET.get('new_date')
    if new_date:
        day = new_date
    else:
        day = request.GET.get('day')
    qs = []
    metrics_list = []
    try:
        for name in metric_names:
            try:
                if name not in metrics_list:
                    metrics_list.append(JobData.objects.get(name=name, obj_type=METRIC))
            except JobData.DoesNotExist:
                raise NotFound(detail=" Cannot Find Metric with name {0} in JobData".format(
                    name))
        qs = metrics_list
        new_qs = []
        # convert qs to a JSON format
        for metric in qs:
            new_qs.append(fill_shell(metric, day))
        print('QS: {}'.format(new_qs))
        return JsonResponse({'name': username, 'children': new_qs}, safe=False)
    except Exception as e:
        logger.error('Could not find user data for user {}: {}'.format(username, e))
        return JsonResponse({}, safe=False)


@login_required
def user_data_view(request):
    return render(request, 'zelda/tree.html')


def get_expt_metadata(expt_id):
    metric_group = []
    categories = [m.category for m in ExptToCategory.objects.filter(expt_group_id=expt_id)]
    for cat in categories:
        metric_group.append(MetricGroupToCategory.objects.filter(category=cat))
    metric_group = [m.metric_group.id for m in metric_group[0]]
    return metric_group


def check_ls_dependencies(name):
    """
    returns dependencies for LS jobs
    """
    deps = []
    try:
        deps = LsTable.objects.get(name=name).dependencies.all()
    except LsTable.DoesNotExist:
        raise NotFound(detail="Cannot find LsTable-{0}".format(name))
    return deps


def get_dependencies(jobs):
    """
    will return corresponding dependency object
    will create new Dependency row if not found
    """
    if not jobs:
        return []
    deps = list()
    for job in jobs:
        if isinstance(job, JobStatus):
            if job.type == METRIC_GROUP or job.type == METRIC_VARIABLE:
                try:
                    curr_dep = Dependency.objects.get(dependency=job.job, job_type=job.type)
                except Dependency.DoesNotExist:
                    curr_dep = Dependency(dependency=job.job, job_type=job.type)
                    curr_dep.save()
            else:
                try:
                    curr_dep = Dependency.objects.get(dependency=job.code, job_type=job.type)
                except Dependency.DoesNotExist:
                    curr_dep = Dependency(dependency=job.code, job_type=job.type)
                    curr_dep.save()
            if curr_dep:
                deps.append(curr_dep)
        elif isinstance(job, basestring):
            try:
                curr_dep = Dependency.objects.filter(dependency=job)
            except Dependency.DoesNotExist:
                curr_dep = Dependency(dependency=job.job, job_type=job.type)
                curr_dep.save()
            if curr_dep:
                deps.append(curr_dep)
        elif isinstance(job, Metric):
            try:
                curr_dep = Dependency.objects.get(dependency=job.code, job_type=METRIC)
            except Dependency.DoesNotExist:
                curr_dep = Dependency(dependency=job.code, job_type=METRIC)
                curr_dep.save()
            if curr_dep:
                deps.append(curr_dep)
        elif isinstance(job, MetricGroup):
            try:
                curr_dep = Dependency.objects.get(dependency=job.code, job_type=METRIC_GROUP)
            except Dependency.DoesNotExist:
                curr_dep = Dependency(dependency=job.code, job_type=METRIC_GROUP)
                curr_dep.save()
            if curr_dep:
                deps.append(curr_dep)
        elif isinstance(job, LsTable):
            try:
                curr_dep = Dependency.objects.get(dependency=job.name, job_type=LISTENER_SUMMARY)
            except Dependency.DoesNotExist:
                curr_dep = Dependency(dependency=job.name, job_type=LISTENER_SUMMARY)
                curr_dep.save()
            if curr_dep:
                deps.append(curr_dep)
        elif isinstance(job, Dependency):
            try:
                curr_dep = Dependency.objects.filter(dependency=job.dependency)
            except Dependency.DoesNotExist:
                curr_dep = []
            if not curr_dep:
                new_dep = Dependency(dependency=job.dependency)
                new_dep.save()
                deps.append(new_dep)
            else:
                deps.append(curr_dep[0])

    return deps


def get_job_data(job_obj, type=""):
    """
    gets data for all job types
    will be called in the populatee.py script
    :param job_obj: name of job
    :return: Data on respective job
    """
    # return ALL jobs for date param
    if type == JOB:
        # find job in JobStatus table
        job_history = JobStatus.objects.filter(job=job_obj)
        # get the most recent job
        recent_job = sorted(job_history, key=lambda x: x.start_day, reverse=True)[0]

        if not job_history:
            return

        if recent_job.type == HIVE_LISTENER_SUMMARY or recent_job.type == LISTENER_SUMMARY:
            dependency_list = check_ls_dependencies(recent_job.job)
        else:
            # get hardcoded dep list for specific job
            # CrossSegmentCount, Baseline, BaselineInit, ExposureRollup, BaselineDenormalizer, AnalyticsJob
            dependency_list = dependencies[recent_job.type]
        type = recent_job.type
        up_dependencies = get_dependencies(dependency_list)
        recent_job = recent_job.job
    elif type == LISTENER_SUMMARY:
        up_dependencies = check_ls_dependencies(job_obj)
        recent_job = job_obj
        type = LISTENER_SUMMARY
    elif type == METRIC_GROUP:
        # MetricVar  w / same name is the  upstream dep
        dependency_list = [JobData(name=job_obj, obj_type=METRIC_VARIABLE)]
        up_dependencies = get_dependencies(dependency_list)
        type = METRIC_GROUP
        recent_job = job_obj
    elif type == METRIC:
        try:
            recent_job = Metric.objects.get(code=job_obj)
        except Metric.DoesNotExist:
            raise NotFound(detail="Could not find {0}-{1}".format(type, job_obj))

        dependency_list = recent_job.metric_group.all()
        up_dependencies = get_dependencies(dependency_list)
        recent_job = recent_job.code
    elif type == EXPERIMENT:
        try:
            if job_obj > 10000:
                recent_job = Experiment.objects.get(experiment_id=job_obj)
                id = recent_job.experiment_id
                recent_job = recent_job.key
            else:
                recent_job = EFExperimentGroup.objects.get(experiment_group_id=job_obj)
                id = recent_job.experiment_group_id
                recent_job = recent_job.name
        except Experiment.DoesNotExist or EFExperimentGroup.DoesNotExist:
            print "COULDNT FIND EXPT: {0}".format(job_obj)
            return

        exp_to_cat = ExptToCategory.objects.filter(expt_group_id=id).all()
        categories = [m.category for m in exp_to_cat]
        cat_to_metric_group = list(itertools.chain.from_iterable(
            [m for m in [MetricGroupToCategory.objects.filter(category=qry).all() for qry in categories]]))
        subbed_metrics = list(itertools.chain.from_iterable(
            [m.metric_group.metrics.all() for m in cat_to_metric_group]))
        dependency_list = subbed_metrics
        up_dependencies = get_dependencies(dependency_list)
    elif type == METRIC_VARIABLE:
        recent_job = job_obj
        dependency_list = set([mv.table for mv in MetricVariable.objects.filter(id__in=MetricVariableToMetric.objects.filter(metric_id__in=[m.id for m in MetricGroup.objects.get(code=job_obj).metrics.all()]).values_list('variable_id', flat=True))])

        up_dependencies = get_dependencies(dependency_list)

    if any(isinstance(el, list) for el in up_dependencies):
        # if it contains any lists then combine all lists into one
        up_dependencies = list(itertools.chain.from_iterable(up_dependencies))
        return {'object': recent_job, "upstream_dep": up_dependencies, 'job_type': type}
    else:
        return {'object': recent_job, "upstream_dep": up_dependencies, 'job_type': type}
