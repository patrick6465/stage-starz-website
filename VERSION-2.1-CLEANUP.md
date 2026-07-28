# Ship-it-Shop Version 2.1 Cleanup

## Completed foundation work

- Railway continues deploying the `railway-deployment` branch.
- The main Stage Starz website is served from `/site`.
- Original website assets remain available through `/assets`.
- The Ship-it-Shop storefront remains available at `/store`.
- Branded 404 and 500 error pages are installed.
- `backup_store.py` exports store records and uploaded image data to a timestamped ZIP archive.

## Backup command

```bash
python backup_store.py
```

Set `BACKUP_DIR` to save the ZIP into a mounted Railway volume or another persistent path:

```bash
BACKUP_DIR=/data/backups python backup_store.py
```

Railway's normal application filesystem is temporary. Production backups must be written to a persistent volume or transferred to external storage.

## Next cleanup stages

1. Extract shared Stage Starz header/footer components.
2. Standardize website and store navigation.
3. Consolidate duplicated website assets after link verification.
4. Add an authenticated admin backup/download screen.
5. Schedule backups after a persistent Railway volume is attached.

Large directory moves should be completed only after the above routes and backups are verified in production.
