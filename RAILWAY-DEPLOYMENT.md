# Stage Starz Railway Deployment

This branch is for private Railway testing. It does not replace the Wix website or the GitHub Pages `main` branch.

## Railway service settings

1. Create a Railway project from `patrick6465/stage-starz-website`.
2. Select the `railway-deployment` branch.
3. Add a persistent volume mounted at `/data`.
4. Add these variables:

- `SECRET_KEY`: a long random value
- `ADMIN_USERNAME`: your private admin username
- `ADMIN_PASSWORD`: a strong unique password
- `DATABASE_PATH`: `/data/store.db`
- `FLASK_ENV`: `production`

Railway reads `railway.toml` and starts the app with Gunicorn.

## Test addresses

- Website: `/`
- Store: `/store`
- Admin: `/admin/login`
- Health check: `/health`

## Important

Do not use the temporary default admin password in production. The database must use the `/data` volume or product changes can be lost during redeployment.
