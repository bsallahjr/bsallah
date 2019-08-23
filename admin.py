from django.contrib import admin

from zelda.models import (JobData)


class JobDataDependency(admin.TabularInline):
    model = JobData.upstream_dep.through
    extra = 0


class JobDataAdmin(admin.ModelAdmin):
    actions = ()
    list_display = ('name', 'obj_type', 'status', 'time_stamp')
    inlines = (JobDataDependency, )
    search_fields = ('name', 'obj_type', 'status', 'time_stamp')


admin.site.register(JobData, JobDataAdmin)

