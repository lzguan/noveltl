FROM ghcr.io/pnpm/pnpm:12.16.1 AS runtime

SHELL [ "/bin/bash", "-c" ]

ARG GNAME=newgroup
ARG UNAME=newuser
ARG NODE_VERSION=26
ARG UID=1000
ARG GID=1000

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
ENV SHELL=bash
ENV ENV=/home/${UNAME}/.bashrc

RUN groupadd -r -g ${GID} ${GNAME} && useradd -ms /bin/bash ${UNAME} -u ${UID} -g ${GNAME}
RUN pnpm setup
RUN pnpm runtime set node ${NODE_VERSION} -g
RUN chown ${UNAME}:${GNAME} /pnpm -R

RUN mkdir -p /home/${UNAME}/.pnpm-store/v11 \
    && chown ${UNAME}:${GNAME} -R /home/${UNAME}/.pnpm-store/v11

USER ${UNAME}

WORKDIR /home/${UNAME}/reader

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

# Development: the full dependency set and the Vite dev server (port 5173).
FROM runtime AS base

RUN pnpm install --frozen-lockfile --store-dir=/home/${UNAME}/.pnpm-store

COPY --chown=${UNAME}:${GNAME} . .
EXPOSE 5173
CMD pnpm run dev

FROM base AS build
RUN pnpm build

# Production: server-side rendering needs Node at runtime, so this serves the
# build with react-router-serve (port 3000, or $PORT) instead of a static server.
FROM runtime AS production

ENV NODE_ENV=production
RUN pnpm install --prod --frozen-lockfile --store-dir=/home/${UNAME}/.pnpm-store
COPY --from=build --chown=${UNAME}:${GNAME} /home/${UNAME}/reader/build ./build
EXPOSE 3000
CMD pnpm run start
