#!/bin/bash

array=(alexinliu richardjli alexdu jackyai shiwenli xaelpeng shiboshen tktian kevinan boyinchen xingsongpan phongchen ganicahyono)

for(( i=0;i<${#array[@]};i++))
do
    echo ${array[i]};
	git -c diff.renameLimit=60000 log --name-only --oneline --author=${array[i]} | grep "^Engine" | grep -v "Engine/Plugins/Aether" | grep -v "DistributedDS" | sort | uniq > ${array[i]}.txt
	
	# 清空结果文件，或者初始化它
	> ${array[i]}_result.txt 

	# 从name.txt读取每一行
	while IFS= read -r line
	do
		# 对每个文件执行git blame操作，然后通过grep过滤出包含‘name’的行，结果追加到result.txt文件
		git blame "$line" | grep ${array[i]} >> ${array[i]}_result.txt
	done < ${array[i]}.txt

done;