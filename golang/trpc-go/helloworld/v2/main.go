// Package main implements a server for Greeter service.
package main

import (
	"context"

	"git.code.oa.com/trpc-go/trpc-go/codec"
	"git.code.oa.com/trpc-go/trpc-go/filter"
	"git.code.oa.com/trpc-go/trpc-go/log"
	"git.code.oa.com/trpc-go/trpc-go/server"

	trpc "git.code.oa.com/trpc-go/trpc-go"
	pb "git.code.oa.com/trpcprotocol/test/helloworld"

	_ "git.code.oa.com/trpc-go/trpc-config-tconf"
	_ "git.code.oa.com/trpc-go/trpc-filter/recovery"
	_ "git.code.oa.com/trpc-go/trpc-filter/validation"
	_ "git.code.oa.com/trpc-go/trpc-log-atta"
	_ "git.code.oa.com/trpc-go/trpc-metrics-m007"
	_ "git.code.oa.com/trpc-go/trpc-naming-polaris"
	_ "git.code.oa.com/trpc-go/trpc-opentracing-tjg"
)

// atta remote logging
var attaFieldFilter = func(ctx context.Context, req, rsp interface{}, handler filter.HandleFunc) error {
	msg := codec.Message(ctx)
	if msg.DyeingKey() == "" {
		msg.WithDyeingKey("dyeing-test-misaka")
	}

	log.WithContextFields(ctx, "uid", msg.DyeingKey(), "cmd", msg.ServerRPCName())

	return handler(ctx, req, rsp)
}

func main() {
	s := trpc.NewServer(server.WithFilter(attaFieldFilter))

	pb.RegisterGreeterService(s, &GreeterServerImpl{})

	if err := s.Serve(); err != nil {
		panic(err)
	}
}
