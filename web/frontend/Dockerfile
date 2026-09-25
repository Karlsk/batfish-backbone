FROM node:25-alpine3.23@sha256:ad82ecad30371c43f4057aaa4800a8ed88f9446553a2d21323710c7b937177fc AS build
WORKDIR /app
RUN npm install --global pnpm@11.19.0
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build
FROM nginx:alpine@sha256:54f2a904c251d5a34adf545a72d32515a15e08418dae0266e23be2e18c66fefa
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/proxy.conf /etc/nginx/nginx.conf
USER 101:101
ENTRYPOINT ["nginx", "-g", "daemon off;"]
