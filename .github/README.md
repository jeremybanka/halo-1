# CI credentials

The Linux build runs inside `archlinux:latest`. GitHub pulls this job container
before executing workflow steps, so Docker Hub credentials are configured in
`jobs.linux.container.credentials` in `workflows/build.yml`.

Add these repository **Actions secrets** under **Settings → Secrets and
variables → Actions**:

- `DOCKERHUB_USERNAME`: the Docker Hub account username.
- `DOCKERHUB_TOKEN`: a Docker Hub personal access token with **Read** permission.

Create the token in Docker account settings with a descriptive name such as
`halo-1-ci`, and choose an expiration appropriate for CI. Store it directly in
GitHub's secret form; never commit it. Replace the secret when rotating the token.
Adding or changing a secret does not start a build; push a workflow change or
rerun the affected job afterward.

References: [GitHub job-container credentials](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idcontainercredentials)
and [Docker personal access tokens](https://docs.docker.com/security/access-tokens/personal-access-tokens/).
