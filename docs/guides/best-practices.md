# Best Practices

## Security

- Enable PII Shield for all external API calls
- Rotate API keys every 90 days
- Use network policies to isolate app namespaces

## Performance

- Monitor resource usage with `kubectl top`
- Scale replicas based on CPU/memory metrics
- Use Redis caching for frequently accessed data

## Data Management

- Schedule regular database backups
- Archive old data to cold storage
- Test restore procedures monthly

## Upgrades

- Test upgrades in a staging environment first
- Read the [changelog](../releases/changelog) before upgrading
- Keep the app within one major version of the platform
