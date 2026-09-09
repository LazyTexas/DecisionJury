# DecisionJury 前端镜像：Node 构建静态资源 → Nginx 托管并反代后端
# 构建上下文：frontend/ 目录
#   docker build -t decisionjury-frontend ./frontend

# ---------- 构建阶段 ----------
FROM node:20-alpine AS build

ARG NPM_REGISTRY=https://registry.npmmirror.com

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm config set registry ${NPM_REGISTRY} && npm ci

COPY . .
# package.json 的 build = tsc -b && vite build
RUN npm run build

# ---------- 运行阶段 ----------
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
