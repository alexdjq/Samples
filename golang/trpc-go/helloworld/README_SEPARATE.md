# 独立客户端和服务器端进程

本项目现在包含两个独立的可执行程序：

## 服务器端 (server/)

### 启动服务器：
```bash
cd server
go run main.go
```

服务器将在默认端口启动（通常是8000），监听Greeter服务的请求。

## 客户端 (client/)

### 使用北极星寻址（默认）：
```bash
cd client
go run main.go "Hello from client"
```

### 使用北极星寻址（自定义命名空间和服务名）：
```bash
cd client
go run main.go polaris Development trpc.misakachen111.helloworld.Greeter1 "Hello from client"
```

### 使用IP直连：
```bash
cd client
go run main.go ip ip://127.0.0.1:8000 "Hello from client"
```

## 项目结构
```
helloworld/
├── server/           # 独立的服务器端项目
│   ├── go.mod       # 服务器端模块定义
│   └── main.go      # 服务器端主程序
├── client/           # 独立的客户端项目
│   ├── go.mod       # 客户端模块定义
│   └── main.go      # 客户端主程序
├── stub/             # Protobuf生成的代码
├── greeter.go        # 原始服务实现（已整合到server/main.go）
├── main.go           # 原始主程序（已简化）
└── server.go         # 原始服务器代码（已整合到server/main.go）
```

## 依赖说明
- 服务器端和客户端都依赖相同的protobuf定义
- 每个目录都有自己的go.mod文件，可以独立构建和运行
- 通过replace指令指向本地的stub目录

## 测试
您可以先启动服务器，然后在另一个终端中运行客户端来测试通信。