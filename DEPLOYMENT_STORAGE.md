# Persistent database storage on Railway

This application uses SQLite. Railway service files are ephemeral unless stored on a mounted volume.

## Required Railway setup

1. Open the Stage Starz service in Railway.
2. Add a Volume to this service.
3. Set the volume mount path to `/app/data`.
4. Redeploy the service.

The application will save its database at `/app/data/store.db`.

Alternatively, when Railway provides `RAILWAY_VOLUME_MOUNT_PATH`, the application automatically stores `store.db` inside that mounted directory.

## Optional explicit configuration

Set `DATABASE_PATH` to an absolute file path inside the mounted volume, for example:

```
DATABASE_PATH=/app/data/store.db
```

Do not mount over `/app`, because that can hide application files. Mount only the data directory.
