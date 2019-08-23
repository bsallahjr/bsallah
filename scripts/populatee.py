import django
django.setup()
from abmetrics_django.models import *
from collections import Iterable
from ab_scheduler.models import *
from ab_scheduler.constants import METRIC_VARIABLE, METRIC_GROUP, METRIC, EXPERIMENT,LISTENER_SUMMARY,JOB
from zelda.models import JobData
all_jobs = list(set([m.job for m in JobStatus.objects.all()]))
from zelda.views import get_job_data, dependencies, get_user_data
from ab_shared.basic_util import num_list_to_text


def uniques(lst): return list(set(lst))


def create_dependencies(name, type=''):
    find_dep = Dependency.objects.filter(dependency=name, job_type=type)
    if find_dep:
        find_dep = find_dep[0]
        if find_dep.job_type != type:
            find_dep.job_type = type
            find_dep.save()
            print 'changed type for:' + type + ':' + name
        print type + ':' + name + " already exists"
    else:
        new_dep = Dependency(dependency=name, job_type=type)
        new_dep.save()
        print 'created: ' + type + ':' + name


def update_all_dependencies():

    metric_variables = uniques([met.job for met in JobStatus.objects.filter(type=METRIC_VARIABLE)])
    for s in metric_variables:
        create_dependencies(s, METRIC_VARIABLE)
    metric_groups = uniques([mets.job for mets in JobStatus.objects.filter(type=METRIC_GROUP)])
    for a in metric_groups:
        create_dependencies(a, METRIC_GROUP)
    metrics = [metric.code for metric in Metric.objects.all()]
    for f in metrics:
        create_dependencies(f, METRIC)
    ls = [ls.name for ls in LsTable.objects.all()]
    for d in ls:
        create_dependencies(d, LISTENER_SUMMARY)

    """hard coded dependencies"""
    for m in dependencies:
        for dep in dependencies[m]:
            create_dependencies(dep)


def update_job_data():
    job_data_list = []
    all_metrics = [m.code for m in Metric.objects.all()]
    all_metric_variables = [m.code for m in MetricGroup.objects.all()]
    all_other_jobs = uniques([m.job for m in JobStatus.objects.all()
                              if m.type != METRIC_VARIABLE and m.type != METRIC_GROUP and m.type != LISTENER_SUMMARY])
    all_experiments = uniques([m.expt_group_id for m in ExptGroupOwner.objects.all()])
    all_ls = [m.name for m in LsTable.objects.all()]

    for name in all_ls:
        job_data_list.append(get_job_data(name, LISTENER_SUMMARY))

    for name in all_metrics:
        job_data_list.append(get_job_data(name, METRIC))

    # for name in all_experiments:
    #     job_data_list.append(get_job_data(name, EXPERIMENT))

    for name in all_metric_variables:

        job_data_list.append(get_job_data(name, METRIC_VARIABLE))
        job_data_list.append(get_job_data(name, METRIC_GROUP))

    for name in all_other_jobs:
        job_data_list.append(get_job_data(name, JOB))

    """
    first iteration will create any unentered JobData objects
    """
    for x in job_data_list:
        if x:
            try:
                curr = JobData.objects.get(name=x['object'], obj_type=x['job_type'])
            except JobData.DoesNotExist:
                curr = []
            if not curr:
                # create JobData if it doesnt exist
                new_job_data = JobData(name=x['object'], obj_type=x['job_type'])
                new_job_data.save()
                for dep in x['upstream_dep']:
                    # if dep not in new_job_data.upstream_dep.all():
                    # import pdb
                    # pdb.set_trace()
                    print type(dep)
                    [new_job_data.upstream_dep.add(d) for d in dep]
                    new_job_data.save()
            else:
                print curr
                for dep in x['upstream_dep']:
                    # add dependencies if they dont exist
                    if dep not in curr.upstream_dep.all():
                        print dep
                        # check if you have a list
                        if isinstance(dep,Iterable):
                            [curr.upstream_dep.add(d) for d in dep]
                        else:
                            curr.upstream_dep.add(dep)


if __name__ == '__main__':
    print update_job_data()



