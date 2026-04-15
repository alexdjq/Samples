package main

import (
	"fmt"
	"sort"
	"time"
)

type BuildConfigItem struct {
	Id                     string `yaml:"Id"`
	Version                string `yaml:"Version"`
	PackageDownloadPath    string `yaml:"PackageDownloadPath"`
	GameserverRelativePath string `yaml:"GameserverRelativePath"`
	Desc                   string `yaml:"Desc"`
	CreateTime             string `yaml:"CreateTime"` // e.g., "2024-03-30T15:04:05Z"
}

func main() {
	list := []BuildConfigItem{
		{Id: "1", CreateTime: "2024-03-30T15:04:05Z"},
		{Id: "2", CreateTime: "2025-01-10T10:00:00Z"},
		{Id: "3", CreateTime: "2023-12-25T08:00:00Z"},
	}

	// 排序，按 CreateTime 降序
	sort.Slice(list, func(i, j int) bool {
		ti, _ := time.Parse(time.RFC3339, list[i].CreateTime)
		tj, _ := time.Parse(time.RFC3339, list[j].CreateTime)
		return ti.After(tj) // 降序：时间晚的排前面
	})

	for _, item := range list {
		fmt.Printf("%s: %s\n", item.Id, item.CreateTime)
	}
}
