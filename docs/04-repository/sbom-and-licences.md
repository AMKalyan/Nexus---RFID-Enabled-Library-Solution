# SBOM and Licence Inventory (D4, NFR 04)

Software bill of materials for release 1.0.1 (bundle `nexus-1.0.1.zip`, tag `v1.0.1`). All versions are pinned:
- `backend/requirements.txt`, `device-sim/requirements.txt` and `migration/requirements.txt` use exact `==` pins.
- `frontend/package-lock.json` locks the frontend dependencies.
- Docker base images carry explicit tags.

Each bundle also carries the pinned files under `sbom/`, together with the source commit.

## How this inventory was produced

| Component | Method |
|---|---|
| API and simulator (Python) | Package metadata read with `importlib.metadata` inside the shipped `nexus-api:1.0.1` and `nexus-devsim:1.0.1` images, in throwaway containers. This covers what is actually deployed, without development or test tooling. The licence comes from `License-Expression`, then the licence classifiers, then the `License` field. `pip-licenses` 5.0.0 was tried first but reports packages that only declare `License-Expression` as `UNKNOWN` |
| Web UI (JavaScript) | `npx license-checker-rseidelsohn@4.4.2 --production` in `frontend/`. These packages are compiled into the static bundle that nginx serves. Build tools are not shipped. The project's own package (`nexus-frontend`, private) is excluded |
| Operating system and servers | Read from the images: `/etc/debian_version`, `/etc/alpine-release`, `dpkg-query`, `nginx -v`, `postgres --version` |

## Container images

| Image | Base | Shipped | Notable contents | Licence of the main component |
|---|---|---|---|---|
| `nexus-api` | `python:3.12.7-slim` (Debian 12.8) | Yes | Python 3.12.7, `postgresql-client-16` 16.15 (PGDG), OpenSSL 3.0.15, ca-certificates | Python: PSF-2.0. PostgreSQL client: PostgreSQL Licence. OpenSSL 3: Apache-2.0 |
| `nexus-web` | `nginx:1.27.2-alpine` (Alpine 3.20.3) | Yes | nginx 1.27.2 serving the compiled UI | nginx: BSD-2-Clause |
| `postgres` | `postgres:16.4-alpine` (Alpine 3.20.3) | Yes | PostgreSQL 16.4 | PostgreSQL Licence |
| `nexus-devsim` | `python:3.12.7-slim` | Yes (demonstration profile only) | Device simulator | PSF-2.0 |
| UI build stage | `node:22.14-alpine` | No (build only) | Node.js 22.14, Vite | MIT |

Operating-system packages inside the base images (Debian and Alpine) keep their own licences. Most are GPL, LGPL, MIT or BSD. They are redistributed unmodified, inside the image archive.

## Copyleft and notice obligations

| Component | Licence | Use in Nexus | Obligation |
|---|---|---|---|
| psycopg, psycopg-binary 3.2.3 | LGPL-3.0 | Database driver, used unmodified as a dynamically loaded library | Keep the licence text (shipped inside the package), and allow the library to be replaced. Both are satisfied by the unmodified wheel inside the image |
| certifi | MPL-2.0 | CA certificate bundle, unmodified | Keep the notice. Source is available upstream |
| Debian and Alpine system packages | Various (GPL, LGPL, …) | Unmodified base OS of the images | Corresponding source is available from the Debian and Alpine archives. Record the image digests with each release |

No dependency's licence restricts commercial use. No GPL-licensed library is linked into the application code.

## Offline installation and redistribution notes

- **The offline bundle redistributes the images listed above.** It must keep these notices and the `sbom/` folder.
- **Docker is not redistributed.** The host needs Docker Engine (a Linux host or VM) or Docker Desktop. Docker Desktop has its own subscription terms for larger organisations and is not supported on Windows Server. On Windows Server, use a Linux VM or a supported container runtime ([environment checklist](../07-deployment/environment-checklist.md)). Check the current licensing terms before deployment.
- **Security updates mean a new bundle.** They arrive as a new bundle built from updated pins and base images (`ops/build_bundle.sh`) and are applied with the documented update and rollback procedure. Run `pip-audit` and `npm audit` for each release; the results for this release are in [security checks](../06-testing/security-checks.md).
- **The licence-file mechanism is not a third-party licence.** It covers activation of Nexus itself (FR 12).

## API image: Python packages (runtime)

| Package | Version | Licence | URL |
|---|---|---|---|
| alembic | 1.13.3 | MIT License | https://alembic.sqlalchemy.org |
| annotated-doc | 0.0.5 | MIT | https://github.com/fastapi/annotated-doc |
| annotated-types | 0.8.0 | MIT | https://github.com/annotated-types/annotated-types |
| anyio | 4.15.1 | MIT | https://github.com/agronholm/anyio |
| argon2-cffi | 23.1.0 | MIT |  |
| argon2-cffi-bindings | 26.1.0 | MIT |  |
| certifi | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) | https://github.com/certifi/python-certifi |
| cffi | 2.1.1 | MIT-0 | https://github.com/python-cffi/cffi |
| chardet | 7.6.0 | 0BSD | https://github.com/chardet/chardet |
| click | 8.5.0 | BSD-3-Clause | https://github.com/pallets/click/ |
| defusedxml | 0.7.1 | Python Software Foundation License | https://github.com/tiran/defusedxml |
| Deprecated | 3.0.0 | MIT | https://github.com/laurent-laporte-pro/deprecated |
| et_xmlfile | 2.0.0 | MIT License | https://foss.heptapod.net/openpyxl/et_xmlfile |
| Faker | 30.1.0 | MIT License | https://github.com/joke2k/faker |
| fastapi | 0.142.2 | MIT | https://github.com/fastapi/fastapi |
| greenlet | 3.5.6 | MIT AND PSF-2.0 | https://greenlet.readthedocs.io |
| h11 | 0.16.0 | MIT License | https://github.com/python-hyper/h11 |
| httpcore | 1.0.9 | BSD-3-Clause | https://www.encode.io/httpcore/ |
| httptools | 0.8.0 | MIT | https://github.com/MagicStack/httptools |
| httpx | 0.27.2 | BSD-3-Clause | https://github.com/encode/httpx |
| idna | 3.20 | BSD-3-Clause | https://github.com/kjd/idna |
| limits | 5.8.0 | MIT | https://limits.readthedocs.org |
| Mako | 1.4.3 | MIT | https://www.makotemplates.org/ |
| MarkupSafe | 3.0.4 | BSD-3-Clause | https://github.com/pallets/markupsafe/ |
| openpyxl | 3.1.5 | MIT License | https://openpyxl.readthedocs.io |
| opentelemetry-api | 1.45.1 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | https://github.com/pypa/packaging |
| pillow | 12.3.0 | MIT-CMU | https://python-pillow.github.io |
| psycopg | 3.2.3 | GNU Lesser General Public License v3 (LGPLv3) | https://psycopg.org/psycopg3/ |
| psycopg-binary | 3.2.3 | GNU Lesser General Public License v3 (LGPLv3) | https://psycopg.org/psycopg3/ |
| pycparser | 3.0 | BSD-3-Clause | https://github.com/eliben/pycparser |
| pydantic | 2.9.2 | MIT | https://github.com/pydantic/pydantic |
| pydantic-settings | 2.5.2 | MIT | https://github.com/pydantic/pydantic-settings |
| pydantic_core | 2.23.4 | MIT License | https://github.com/pydantic/pydantic-core |
| PyJWT | 2.15.1 | MIT | https://github.com/jpadilla/pyjwt |
| python-dateutil | 2.9.0.post0 | BSD License; Apache Software License | https://github.com/dateutil/dateutil |
| python-dotenv | 1.2.4 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| python-multipart | 0.0.32 | Apache-2.0 | https://github.com/Kludex/python-multipart |
| PyYAML | 6.0.2 | MIT License | https://pyyaml.org/ |
| reportlab | 4.2.2 | BSD License | https://www.reportlab.com/ |
| six | 1.17.0 | MIT License | https://github.com/benjaminp/six |
| slowapi | 0.1.9 | MIT License | https://github.com/laurents/slowapi |
| sniffio | 1.3.1 | MIT License; Apache Software License | https://github.com/python-trio/sniffio |
| SQLAlchemy | 2.0.35 | MIT License | https://www.sqlalchemy.org |
| starlette | 1.7.0 | BSD-3-Clause | https://github.com/Kludex/starlette |
| typing-inspection | 0.4.4 | MIT | https://github.com/pydantic/typing-inspection |
| typing_extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| uvicorn | 0.54.0 | BSD-3-Clause | https://uvicorn.dev/ |
| uvloop | 0.23.0 | Apache Software License; MIT License |  |
| watchfiles | 1.3.0 | MIT License | https://github.com/samuelcolvin/watchfiles |
| websockets | 17.2 | BSD-3-Clause | https://github.com/python-websockets/websockets |
| wrapt | 2.5.0 | BSD-2-Clause | https://github.com/GrahamDumpleton/wrapt |

## Device simulator image: Python packages

| Package | Version | Licence | URL |
|---|---|---|---|
| annotated-doc | 0.0.5 | MIT | https://github.com/fastapi/annotated-doc |
| annotated-types | 0.8.0 | MIT | https://github.com/annotated-types/annotated-types |
| anyio | 4.15.1 | MIT | https://github.com/agronholm/anyio |
| certifi | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) | https://github.com/certifi/python-certifi |
| click | 8.5.0 | BSD-3-Clause | https://github.com/pallets/click/ |
| fastapi | 0.142.2 | MIT | https://github.com/fastapi/fastapi |
| h11 | 0.16.0 | MIT License | https://github.com/python-hyper/h11 |
| httpcore | 1.0.9 | BSD-3-Clause | https://www.encode.io/httpcore/ |
| httpx | 0.27.2 | BSD-3-Clause | https://github.com/encode/httpx |
| idna | 3.20 | BSD-3-Clause | https://github.com/kjd/idna |
| opentelemetry-api | 1.45.1 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api |
| pydantic | 2.13.5 | MIT | https://github.com/pydantic/pydantic |
| pydantic_core | 2.46.5 | MIT | https://github.com/pydantic/pydantic |
| python-multipart | 0.0.32 | Apache-2.0 | https://github.com/Kludex/python-multipart |
| sniffio | 1.3.1 | MIT License; Apache Software License | https://github.com/python-trio/sniffio |
| starlette | 1.7.0 | BSD-3-Clause | https://github.com/Kludex/starlette |
| typing-inspection | 0.4.4 | MIT | https://github.com/pydantic/typing-inspection |
| typing_extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| uvicorn | 0.54.0 | BSD-3-Clause | https://uvicorn.dev/ |

## Web UI: JavaScript packages compiled into the bundle

| Package | Version | Licence | Repository |
|---|---|---|---|
| @reduxjs/toolkit | 2.13.0 | MIT | https://github.com/reduxjs/redux-toolkit |
| @standard-schema/spec | 1.1.0 | MIT | https://github.com/standard-schema/standard-schema |
| @standard-schema/utils | 0.3.0 | MIT | https://github.com/standard-schema/standard-schema |
| @tanstack/query-core | 5.59.0 | MIT | https://github.com/TanStack/query |
| @tanstack/react-query | 5.59.0 | MIT | https://github.com/TanStack/query |
| @types/d3-array | 3.2.2 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-color | 3.1.3 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-ease | 3.0.2 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-interpolate | 3.0.4 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-path | 3.1.1 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-scale | 4.0.9 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-shape | 3.2.0 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-time | 3.0.4 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/d3-timer | 3.0.2 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/prop-types | 15.7.15 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/react | 18.3.31 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/use-sync-external-store | 0.0.6 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| clsx | 2.1.1 | MIT | https://github.com/lukeed/clsx |
| cookie | 1.1.1 | MIT | https://github.com/jshttp/cookie |
| csstype | 3.2.3 | MIT | https://github.com/frenic/csstype |
| d3-array | 3.2.4 | ISC | https://github.com/d3/d3-array |
| d3-color | 3.1.0 | ISC | https://github.com/d3/d3-color |
| d3-ease | 3.0.1 | BSD-3-Clause | https://github.com/d3/d3-ease |
| d3-format | 3.1.2 | ISC | https://github.com/d3/d3-format |
| d3-interpolate | 3.0.1 | ISC | https://github.com/d3/d3-interpolate |
| d3-path | 3.1.0 | ISC | https://github.com/d3/d3-path |
| d3-scale | 4.0.2 | ISC | https://github.com/d3/d3-scale |
| d3-shape | 3.2.0 | ISC | https://github.com/d3/d3-shape |
| d3-time-format | 4.1.0 | ISC | https://github.com/d3/d3-time-format |
| d3-time | 3.1.0 | ISC | https://github.com/d3/d3-time |
| d3-timer | 3.0.1 | ISC | https://github.com/d3/d3-timer |
| decimal.js-light | 2.5.1 | MIT | https://github.com/MikeMcl/decimal.js-light |
| es-toolkit | 1.52.0 | MIT | https://github.com/toss/es-toolkit |
| eventemitter3 | 5.0.4 | MIT | https://github.com/primus/eventemitter3 |
| immer | 11.1.21 | MIT | https://github.com/immerjs/immer |
| internmap | 2.0.3 | ISC | https://github.com/mbostock/internmap |
| js-tokens | 4.0.0 | MIT | https://github.com/lydell/js-tokens |
| loose-envify | 1.4.0 | MIT | https://github.com/zertosh/loose-envify |
| lucide-react | 0.447.0 | ISC | https://github.com/lucide-icons/lucide |
| react-dom | 18.3.1 | MIT | https://github.com/facebook/react |
| react-is | 18.3.1 | MIT | https://github.com/facebook/react |
| react-redux | 9.3.0 | MIT | https://github.com/reduxjs/react-redux |
| react-router-dom | 7.18.4 | MIT | https://github.com/remix-run/react-router |
| react-router | 7.18.4 | MIT | https://github.com/remix-run/react-router |
| react | 18.3.1 | MIT | https://github.com/facebook/react |
| recharts | 3.10.1 | MIT | https://github.com/recharts/recharts |
| redux-thunk | 3.1.0 | MIT | https://github.com/reduxjs/redux-thunk |
| redux | 5.0.1 | MIT | https://github.com/reduxjs/redux |
| reselect | 5.2.0 | MIT | https://github.com/reduxjs/reselect |
| scheduler | 0.23.2 | MIT | https://github.com/facebook/react |
| set-cookie-parser | 2.7.2 | MIT | https://github.com/nfriedly/set-cookie-parser |
| tiny-invariant | 1.3.3 | MIT | https://github.com/alexreardon/tiny-invariant |
| use-sync-external-store | 1.7.0 | MIT | https://github.com/react/react |
| victory-vendor | 37.3.6 | MIT AND ISC | https://github.com/FormidableLabs/victory |
