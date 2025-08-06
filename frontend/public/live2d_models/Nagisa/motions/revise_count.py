import json

# 读取 Motion3 JSON 文件
file_n = "Idle.motion3.json"
with open(file_n, "r", encoding="utf-8") as f:
    motion_data = json.load(f)

# 重新计算 CurveCount、TotalSegmentCount、TotalPointCount
motion_data["Meta"]["CurveCount"] = len(motion_data["Curves"])
motion_data["Meta"]["TotalSegmentCount"] = sum(len(curve["Segments"]) // 3 for curve in motion_data["Curves"])
motion_data["Meta"]["TotalPointCount"] = sum(len(curve["Segments"]) // 2 for curve in motion_data["Curves"])

# 将修正后的 JSON 保存
with open(file_n, "w", encoding="utf-8") as f:
    json.dump(motion_data, f, indent=2, ensure_ascii=False)

print(f"修正完成，已保存为 {file_n}")
