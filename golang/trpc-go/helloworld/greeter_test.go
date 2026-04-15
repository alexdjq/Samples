package main

import (
	"fmt"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"

	trpc "git.code.oa.com/trpc-go/trpc-go"
	pb "git.code.oa.com/trpcprotocol/test/helloworld"
)

func TestMain(m *testing.M) {
	go func() {
		main()

	}()
	time.Sleep(time.Second)
	m.Run()
}

func TestHelloworld(t *testing.T) {

	proxy := pb.NewGreeterClientProxy()

	req := &pb.HelloRequest{
		Msg: "trpc-go-client",
	}
	for i := 0; i < 10; i++ {
		rsp, err := proxy.SayHello(trpc.BackgroundContext(), req)
		assert.NotNil(t, err)
		assert.Nil(t, rsp)
		fmt.Printf("rsp: %s, err: %v", rsp, err)
		time.Sleep(time.Second)
	}
}
