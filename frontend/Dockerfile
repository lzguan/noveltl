FROM node:22-bookworm-slim

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
ENV npm_config_store_dir=/pnpm/store
ENV CI=true

ARG GNAME=newuser
ARG UNAME=newuser
ARG UID=1001
ARG GID=1001

RUN groupadd -r -g ${GID} ${GNAME} && useradd -u ${UID} -ms /bin/bash ${UNAME} -g ${GNAME}

RUN npm install --global corepack@latest --force
RUN corepack enable pnpm
RUN mkdir /home/${UNAME}/.pnpm-store/v11 -p && chown ${UNAME}:${GNAME} /home/${UNAME}/.pnpm-store -R
RUN chown ${UNAME}:${GNAME} /home/${UNAME} -R
USER ${UNAME}

WORKDIR /home/${UNAME}/frontend


COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

RUN --mount=type=cache,id=pnpm,target=/home/${UNAME}/.pnpm-store,uid=${UID},gid=${GID} pnpm install --frozen-lockfile --force

COPY . .
EXPOSE 5173
CMD pnpm run dev
