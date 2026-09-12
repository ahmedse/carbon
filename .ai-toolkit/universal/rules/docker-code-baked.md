## Docker: Code is Baked in the Image

```
rsync to host       → does NOT update running container
docker restart      → does NOT re-pull host code
Code lives at /app in the container, baked into image at build time
```

### Hotfix a Single File
```bash
docker cp /local/path/file.py <PROD_CONTAINER>:/app/path/in/container/file.py
docker restart <PROD_CONTAINER>

# MANDATORY VERIFY — if this returns 0, the deploy failed:
docker exec <PROD_CONTAINER> grep -c "<marker_string>" /app/path/in/container/file.py
```

### Proper Fix (code baked in image)
Use the project's deploy script. Do not improvise deploy steps.
```bash
ls deploy/   # find the deploy script first
```

`docker cp` is a hotfix. It is LOST on the next `docker run` / `docker compose up`.

---

*Source: ~/ai-toolkit/universal/rules/docker-code-baked.md*
