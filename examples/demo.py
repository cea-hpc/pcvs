from pcvs.dsl import Bank, Serie, Run, Job

# open a bank
bank = Bank('./demo.git')

# retrieve project/configs within the bank
# a given serie is identified by:
# - a name 
# - a hash, based on a specific profile
list_of_projects = bank.list_projects()
configs_for_project = bank.list_series(list_of_projects[0])
serie = bank.get_serie(configs_for_project[0])

# Modifiers
job_list = serie.find(Serie.Request.REGRESSIONS, since=None, until=None)

# Create a run to edit
run = Run(serie)

# mark each failed jobs as success
for job in job_list:
    job.status = Job.State.SUCCESS
    run.update(job.name, job)

# save the run as the last one for this serie
serie.commit(run)
