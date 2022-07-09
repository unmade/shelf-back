# Running on Heroku

The project can be run on Heroku with limited capabilities.

Unfortunately, Heroku doesn't support EdgeDB, which is required to run the
project. There is also
[heroku-buildpack-edgedb](https://elements.heroku.com/buildpacks/edgedb/heroku-buildpack-edgedb)
, but it doesn't seem to work.

One workaround is to have EdgeDB server right in the Docker image next to the
application server/celery and then use it as a frontend for the Heroku Postgres
addon.

Note, the `start-edgedb` command automatically parses `DATABASE_URL` environment
variable set by Heroku Postgres addon and there is no need to specify
`DATABASE_DSN` and `DATABASE_TLS_CA_FILE` environment variables.

Other important note is that EdgeDB create more than 20k+ rows and exceeds
the limit of free dyno. Because of that `INSERT` privileges to the database are
automatically revoked in 7 days.
