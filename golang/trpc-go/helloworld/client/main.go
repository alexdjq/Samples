package main

import (
	"fmt"
	"time"

	trpc "git.code.oa.com/trpc-go/trpc-go"
	"git.code.oa.com/trpc-go/trpc-go/client"
	pb "git.code.oa.com/trpcprotocol/test/helloworld"

	_ "git.code.oa.com/trpc-go/trpc-naming-polaris"
)

func main() {

	_ = trpc.NewServer()

	for i := 0; i < 100; i++ {
		req := &pb.HelloRequest{
			Msg: fmt.Sprintf("this is %d message", i),
		}

		version := "v1"
		if i%2 == 0 {
			version = "v2"
		}

		proxy := pb.NewGreeterClientProxy(
			client.WithTarget("polaris://trpc.alexduTest.helloworld.Greeter"),
			client.WithCalleeMetadata("grey_version", version))

		rsp, err := proxy.SayHello(trpc.BackgroundContext(), req)
		if err == nil {
			fmt.Printf("rsp: %s\n", rsp)
		} else {
			fmt.Printf("Error: rsp: %s, err: %v\n", rsp, err)
		}

		time.Sleep(time.Second)
	}
}
