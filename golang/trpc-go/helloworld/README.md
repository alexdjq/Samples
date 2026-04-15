## tRPC-Go helloworld 工程示例

## 业务服务开发步骤：
 - 1. 每个服务单独创建一个git，如：git.woa.com/trpc-go/helloworld
 - 2. 初始化go mod文件：go mod init git.woa.com/trpc-go/helloworld
 - 3. 编写服务协议文件，如：helloworld.proto , 协议规范如下： 
  - 3.1 package分成三级 trpc.app.server，app是一个业务项目分类，server是具体的进程服务名
  - 3.2 必须指定 option go_package，表明协议的git地址
  - 3.3 定义service rpc方法，一个server可以有多个service，一般都是一个server一个service
  - 3.4 定义字段校验规则（推荐、可选），使用方法参考[《使用手册》](https://git.woa.com/devsec/protoc-gen-secv/wikis/%E6%A0%A1%E9%AA%8C%E8%A7%84%E5%88%99/)。本例中，对msg字段做数据校验，格式必须为“字母+数字”组合。
```golang
    syntax = "proto3";
		
    package trpc.test.helloworld;
    option go_package="git.code.oa.com/trpcprotocol/test/helloworld";
    
    // 数据校验校验 - 本地
    import "validate.proto";
    // 数据校验校验 - rick平台编译使用
    //import "trpc/common/validate.proto"; 
    
    service Greeter {
        rpc SayHello (HelloRequest) returns (HelloReply) {}
    }
    
    message HelloRequest {
        // 对msg字段做数据校验，长度必须大于1
        string msg = 1 [(validate.rules).string.min_len = 1];
        // 不做数据校验
        // string msg = 1;
    }
    
    message HelloReply {
        string msg = 1;
    }
 
```
 - 4. 通过命令行生成服务模型（本项目已带，参见stub目录）：trpc create -p helloworld.proto（首先需要先[安装trpc工具](https://git.woa.com/trpc-go/trpc-go-cmdline)）
 - 5. 开发具体业务逻辑
 - 6. 开发完成，开始编译，根目录执行：go build
 - 7. 启动服务：./helloworld &
 - 8. 自测：go test
