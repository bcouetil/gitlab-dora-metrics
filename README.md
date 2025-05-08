
_Code and explanation copied from [a Zenika article on dev.to](https://dev.to/zenika/gitlab-a-python-script-calculating-dora-metrics-258o) for collaboration purpose._

![a humanoid fox from behind watching metrics dashboards, multiple computer monitors,manga style](https://raw.githubusercontent.com/bcouetil/articles/main/images/gitlab/dora/fox-dashboard-1.jpg)

- [Initial thoughts](#initial-thoughts)
- [Considered alternate solutions](#considered-alternate-solutions)
  - [GitLab Value Stream Analytics (official solution)](#gitlab-value-stream-analytics-official-solution)
  - [LinearB (SaaS solution with free tier)](#linearb-saas-solution-with-free-tier)
  - [Four Keys (open source based on GCP)](#four-keys-open-source-based-on-gcp)
- [DORA Metrics and calculations insights](#dora-metrics-and-calculations-insights)
  - [Metric A: Lead Time for Changes](#metric-a-lead-time-for-changes)
  - [Metric B: Deployment Frequency](#metric-b-deployment-frequency)
  - [Metric C: Change Failure Rate](#metric-c-change-failure-rate)
  - [Metric D: Time to Restore Service](#metric-d-time-to-restore-service)
- [The Python script](#the-python-script)
  - [Output example](#output-example)
  - [Pre-requisites](#pre-requisites)

<!-- TOC end -->

# Initial thoughts

The DevOps Research and Assessment (DORA) team has identified four crucial metrics for measuring DevOps performance. Employing these metrics not only enhances DevOps efficiency but also effectively communicates performance to business stakeholders, thereby accelerating business results.

In his insightful article, [DORA Metrics: What are they, and what's new in 2024?](https://dev.to/jreock/dora-metrics-what-are-they-and-whats-new-in-2023-4l50), Justin Reock provides a comprehensive overview of these metrics. By the way, you should also check out the follow-up article, [Developer Experience is Dead: Long Live Developer Experience!](https://dev.to/jreock/developer-experience-is-dead-long-live-developer-experience-1col) 🤓

Embracing [DORA program findings](https://dora.dev/research/), we performed some research on how to obtain these crucial metrics for GitLab projects. The culmination of our exploration is a homemade Python script designed to calculate these metrics for individual projects or an entire group within GitLab, recursively. While the script doesn't generate graphical representations, it serves as a practical tool for periodic metric calculations:

![python-output](https://raw.githubusercontent.com/bcouetil/articles/main/images/gitlab/dora/dora-python-output.jpg)

This script has been executed on a couple of projects and groups across different organizations, yielding interesting results and with little to no effort on the targeted codebase.

Let's now look into the available solutions for GitLab projects, how GitLab officially compute these metrics, and understand the specific metrics our script calculates.

<!-- # The 4 key metrics definitions

![dora-metrics-definitions](https://www.sourcedgroup.com/wp-content/uploads/2022/08/key_dora_metrics_diagram_RGB.svg)

_From [DORA Metrics: Measuring What Really Matters About Your Software Delivery](https://www.sourcedgroup.com/blog/dora-metrics-measuring-what-really-matters-about-your-software-delivery/)_ -->

# Considered alternate solutions

Some alternate solutions have been explored before making a script from scratch.

## GitLab Value Stream Analytics (official solution)

[GitLab official DORA metrics in Value Stream Analytics](https://docs.gitlab.com/ee/user/analytics/dora_metrics.html) is a wonderful way to display the metrics overtime, without much effort.

![gitlab-dora-screenshot](https://raw.githubusercontent.com/bcouetil/articles/main/images/gitlab/dora/dora-gitlab.png)

Regrettably, it is exclusively accessible with the [Ultimate license level](https://about.gitlab.com/pricing/) priced at $99 per developer per month. While it certainly brings value, it may be difficult to convince managers to upgrade to this level.

## LinearB (SaaS solution with free tier)

![linearb-dora-screenshot](https://raw.githubusercontent.com/bcouetil/articles/main/images/gitlab/dora/dora-linearb.jpg)

[LinearB](https://linearb.io/) is a SaaS solution that retrieves metrics overtime, some of them being used to calculate DORA Metrics. They also have a [Youtube channel](https://www.youtube.com/@LinearBInc) that advocate for DORA Metrics and more.

The DORA segment is free, and you should certainly explore it while evaluating solutions in this field.

## Four Keys (open source based on GCP)

[Four Keys](https://github.com/dora-team/fourkeys) is an open source alternative by Google employees that has been halted earlier this year (but forks-friendly).

![fourkeys-dora-dashboard](https://raw.githubusercontent.com/bcouetil/articles/main/images/gitlab/dora/dora-fourkeys-dashboard.png)

This is a complete solution that needs a complex set of GCP resources to store and query the data.

![fourkeys-dora-design](https://raw.githubusercontent.com/bcouetil/articles/main/images/gitlab/dora/dora-fourkeys-design.png)

But we deemed the initial cost too high for initiating DORA Metrics calculation.

![a humanoid fox from behind watching metrics dashboards, multiple computer monitors,manga style](https://raw.githubusercontent.com/bcouetil/articles/main/images/gitlab/dora/fox-dashboard-4.jpg)

# DORA Metrics and calculations insights

We found above existing solutions often had drawbacks, like costs or complex setups. So, to keep things simple and flexible, we built our own tool.

We'll dig into the thinking behind our choice, examining the details of GitLab's official metrics calculations. We'll point out any quirks or limitations and introduce our alternative methods.

We'll break down the four key DORA metrics—Lead Time for Changes, Deployment Frequency, Change Failure Rate, and Time to Restore Service. For each one, we'll compare GitLab's way with ours, making it easy for you to grasp how to get these metrics practically.

## Metric A: Lead Time for Changes

Lead Time for Changes: How long does it take to go from code committed to code successfully running in production?

### GitLab official calculation

How Lead Time for Changes is calculated in [GitLab DORA Metrics](https://docs.gitlab.com/ee/user/analytics/dora_metrics.html):

> GitLab calculates lead time for changes based on the number of seconds to successfully deliver a commit into production: from merge request merge time (when the merge button is clicked) to code successfully running in production, without adding the coding_time to the calculation. Data is aggregated right after the deployment is finished, with a slight delay.

OK, so if a commit has been pushed 2 weeks ago, and we merged an hour ago, and then we deploy to production, the commit age is one hour ? It does not seem quite right.

> By default, lead time for changes supports measuring only one branch operation with multiple deployment jobs (for example, from development to staging to production on the default branch). When a merge request gets merged on staging, and then on production, GitLab interprets them as two deployed merge requests, not one.

This is hard to understand, so what is the LTfC for this commit ? Does it contribute 2 times to the average ? And what about the branch name ? Is it configurable ? The verified branch is `main` or `production` ?

### Our calculation

Our calculation is fairly simple: the average age of commits deployed to production, created after the last successful deployment to production. Excluding merge commits.

The branch names checked are `main` and `master` by default, configurable with a regex.

## Metric B: Deployment Frequency

Deployment Frequency: How often does your organization deploy code to production or release it to end users?

### GitLab official calculation

How Deployment Frequency is calculated in [GitLab DORA Metrics](https://docs.gitlab.com/ee/user/analytics/dora_metrics.html):

> In GitLab, deployment frequency is measured by the average number of deployments per day to a given environment, based on the deployment’s end time (its finished_at property). GitLab calculates the deployment frequency from the number of finished deployments on the given day. Only successful deployments (Deployment.statuses = success) are counted.

This makes sense. But it takes into account bug fixes as valid deployments. If we deploy one feature a week and then deploy fixes everyday until the feature works, are we deploying once a day ? It is debatable, but we do not think so.

> The calculation takes into account the production environment tier or the environments named production/prod. The environment must be part of the production deployment tier for its deployment information to appear on the graphs.

The environment tier is a nice generic solution. `production` / `prod` environment names alternatives are simple and efficient, but will not fit every projects without some change.

### Our calculation

We chose to discard deployments of hotfixes. For now this is simple, even simplistic: if the last commit message starts with `Merge branch 'hotfix`, it is considered a hotfix, then it is not a feature deployment. Later versions of the script could involve regular expression.

For environment names, tier is not taken into account (yet), but a regular expression is used to accommodate to most situations without impacting legacy projects. Default regular expression is _every environment starting with "prod", within a subfolder or not_ (`(|.*\/)prod.*`). We have to be careful not to include `preprod` environments.

## Metric C: Change Failure Rate

Change Failure Rate: What percentage of changes to production or released to users result in degraded service (e.g., lead to service impairment or service outage) and subsequently require remediation (e.g., require a hotfix, rollback, fix forward, patch)?

### GitLab official calculation

Change Failure Rate is calculated in [GitLab DORA Metrics](https://docs.gitlab.com/ee/user/analytics/dora_metrics.html):

> In GitLab, change failure rate is measured as the percentage of deployments that cause an incident in production in the given time period. GitLab calculates this as the number of incidents divided by the number of deployments to a production environment. This assumes:
>
> - GitLab incidents are tracked.
> - All incidents are related to a production environment.
> - Incidents and deployments have a strictly one-to-one relationship. An incident is related to only one production deployment, and any production deployment is related to no more than one incident.

Again, a smart solution for a problem involving something beyond the code: detecting an incident. This presupposes several factors; however, achieving precise accuracy is challenging.

### Our alternative metric calculation: Ratio of Deployments Needing Hotfix(es)

The accuracy with just calculation is challenging. We chose not to involve ticket management, for now.

Instead, we compute the average _Ratio of Deployments Needing Hotfix_. If a hotfix has been performed after a deployment, we consider the deployment resulted in degraded service. While this calculation is not the complete metric, it offers a technical and easily measurable insight.

As for another metric, if the last commit message starts with `Merge branch 'hotfix`, it is considered a hotfix on the previously non-hotfix deployment.

## Metric D: Time to Restore Service

Time to Restore Service: How long does it generally take to restore service when a service incident or a defect that impacts users occurs (e.g., unplanned outage, service impairment)?

### GitLab official calculation

Time to Restore Service is calculated in [GitLab DORA Metrics](https://docs.gitlab.com/ee/user/analytics/dora_metrics.html):

> In GitLab, time to restore service is measured as the median time an incident was open for on a production environment. GitLab calculates the number of seconds an incident was open on a production environment in the given time period. This assumes:
>
> - GitLab incidents are tracked.
> - All incidents are related to a production environment.
> - Incidents and deployments have a strictly one-to-one relationship. An incident is related to only one production deployment, and any production deployment is related to no more than one incident.

A smart solution for a problem involving something beyond the code: detecting an incident. This assumes a lot of things though; The accuracy is challenging.

### Our alternative metric calculation: Last Hotfix Median Delay

Again, the accuracy with just calculation is just too challenging. We chose not to involve ticket management.

Instead, we compute the _Last Hotfix Median Delay_. If there is a hotfix one week after the last successful non-hotfix deployment, it is considered something needed from day one, as a fair approximation. This is not the full compute of the metric, hence not a DORA metric per se, but something technical and easily mesurable.

As for another metric, if the last commit message starts with `Merge branch 'hotfix`, it is considered a hotfix on the previously non-hotfix deployment.

![a humanoid fox from behind watching metrics dashboards, multiple computer monitors,manga style](https://raw.githubusercontent.com/bcouetil/articles/main/images/gitlab/dora/fox-dashboard-3.jpg)

# The Python script

This Python script calculates data for an individual project, a list of projects, or projects within a group recursively, over a specified time span. It doesn't generate graphs or tables; its purpose is straightforward, allowing occasional metric calculations.

Additionally, it serves as an auditing tool, designed to work seamlessly across various project types without requiring modifications.

The script's header provides detailed descriptions of the available arguments.

## Output example

```shell
python compute-dora-metrics.py --token $GITLAB_TOKEN --group-id 10000 --days 180
```

![python-output](https://raw.githubusercontent.com/bcouetil/articles/main/images/gitlab/dora/dora-python-output.jpg)

## Pre-requisites

- Some Python packages installed
  - `pip install requests ansicolors`
- An access to all the projects in the group
- Hotfixes are performed by branches whose name starts with 'hotfix', and merges are performed with a merge commit.
- Deployments are performed using the environment feature, and the production environments are distinguished by a common regex.
