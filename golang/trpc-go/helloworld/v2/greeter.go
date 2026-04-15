package main

import (
	"context"
	"fmt"

	"git.code.oa.com/pcgmonitor/trpc_report_api_go/pb/nmnt"
	"git.code.oa.com/trpc-go/trpc-go/client"
	"git.code.oa.com/trpc-go/trpc-go/codec"
	"git.code.oa.com/trpc-go/trpc-go/config"
	"git.code.oa.com/trpc-go/trpc-go/log"
	"git.code.oa.com/trpc-go/trpc-go/metrics"

	pcgmonitor "git.code.oa.com/pcgmonitor/trpc_report_api_go"
	trpc "git.code.oa.com/trpc-go/trpc-go"
	pb "git.code.oa.com/trpcprotocol/test/helloworld"

	_ "git.code.oa.com/trpc-go/trpc-filter/validation"
)

// GreeterServerImpl implements GreeterServer interface in pb.
type GreeterServerImpl struct{}

// SayHello returns req to rsp.
func (s *GreeterServerImpl) SayHello(ctx context.Context, req *pb.HelloRequest) (*pb.HelloReply, error) {
	fmt.Printf("SayHello v2 was called. req: %v\n", req)
	/*
		log.InfoContextf(ctx, "req: %s", req)

		// Get the value of parameter.
		inputValue := req.Msg

		// Get config from tconf.
		tconfValue := getTconfValue(ctx)

		// tconf kv
		tconfKv := getTconfKv(ctx)

		customMonitor(ctx, tconfValue, tconfKv)

		// Request the trpc service.
		result := callTrpcJava(ctx)

		polarisResult := callByPolarisDiscovery(ctx)

	*/
	// Create response
	rsp := &pb.HelloReply{
		Msg: req.GetMsg(),
	}
	//log.InfoContextf(ctx, "rsp: %s", rsp)

	return rsp, nil
}

// customMonitor customizes the monitoring.
func customMonitor(ctx context.Context, tconfValue, tconfKv string) {
	// Set metrics reporting.
	metrics.Counter("testAttribute").Incr()
	metrics.Counter(tconfValue).Incr()
	metrics.Counter(fmt.Sprintf("%s:%d",
		trpc.GlobalConfig().Server.Service[0].IP, trpc.GlobalConfig().Server.Service[0].Port))
	metrics.Gauge("test-gauge").Set(1.0)

	msg := codec.Message(ctx)
	var dimesions = []string{msg.RemoteAddr().String(), msg.LocalAddr().String(), tconfValue, tconfKv}
	var statValues []*nmnt.StatValue
	statValues = append(statValues, &nmnt.StatValue{Value: 1, Count: 1, Policy: nmnt.Policy_SUM})
	statValues = append(statValues, &nmnt.StatValue{Value: 1, Count: 1, Policy: nmnt.Policy_SUM})
	statValues = append(statValues, &nmnt.StatValue{Value: 1, Count: 1, Policy: nmnt.Policy_SUM})
	statValues = append(statValues, &nmnt.StatValue{Value: 1, Count: 1, Policy: nmnt.Policy_SUM})
	pcgmonitor.ReportCustom("test_custom_1", dimesions, statValues)
}

func getTconfValue(ctx context.Context) string {

	c, err := config.Load("test.yaml", config.WithCodec("yaml"), config.WithProvider("tconf"))
	if err != nil {
		log.ErrorContextf(ctx, "get tconf error: %s", err.Error())
		return fmt.Sprintf("get tconf error: %s", err.Error())
	}
	tconfValue := c.GetString("server.app", "default hello")
	log.InfoContextf(ctx, "tconf value: %s", tconfValue)
	return tconfValue
}

func getTconfKv(ctx context.Context) string {
	c, err := config.Load("test.conf", config.WithCodec("tconf-kv"), config.WithProvider("tconf"))
	if err != nil {
		log.ErrorContextf(ctx, "get tconf kv error: %s", err.Error())
		return fmt.Sprintf("get tconf kv error: %s", err.Error())
	}
	appname := c.GetString("server", "default kv value")
	log.InfoContextf(ctx, "tconf kv value: %s", appname)

	return appname
}

// callTrpcJava calls Java trpc service (cross language example).
func callTrpcJava(ctx context.Context) string {

	opts := []client.Option{
		client.WithTarget("ip://9.24.159.19:18001"),
	}

	clientProxy := pb.NewGreeterClientProxy(opts...)
	req := &pb.HelloRequest{
		Msg: "hello from go",
	}

	rsp, err := clientProxy.SayHello(ctx, req)
	if err != nil {
		log.ErrorContextf(ctx, "call java err: %s", err.Error())
		return fmt.Sprintf("call java err: %s", err.Error())
	}

	log.InfoContextf(ctx, "req:%v, rsp:%v, err:%v", req, rsp, err)
	return rsp.Msg
}

// callByPolarisDiscovery requests service via Polaris service discovery.
func callByPolarisDiscovery(ctx context.Context) string {
	opts := []client.Option{
		client.WithNamespace("Development"),
		client.WithServiceName("trpc.misakachen111.helloworld.Greeter1"),
	}

	clientProxy := pb.NewGreeterClientProxy(opts...)
	req := &pb.HelloRequest{
		Msg: "hello",
	}

	rsp, err := clientProxy.SayHello(ctx, req)
	if err != nil {
		log.ErrorContextf(ctx, "call by polaris discovery  err: %s", err.Error())
		return fmt.Sprintf("call by polaris discovery  err: %s", err.Error())
	}

	log.InfoContextf(ctx, "req:%v, rsp:%v, err:%v", req, rsp, err)
	return rsp.Msg
}
