FROM ghcr.io/pnpm/pnpm:11.10.0 AS base

SHELL [ "/bin/bash", "-c" ]

ARG GNAME=newgroup
ARG UNAME=newuser
ARG NODE_VERSION=22
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

WORKDIR /home/${UNAME}/frontend

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

RUN --mount=type=cache,id=frontend-pnpm-store-v11,target=/home/${UNAME}/.pnpm-store,sharing=locked,uid=${UID},gid=${GID} \
    pnpm install --frozen-lockfile --store-dir=/home/${UNAME}/.pnpm-store

COPY . .
EXPOSE 5173
CMD pnpm run dev
