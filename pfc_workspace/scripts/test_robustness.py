import itasca

print("--- Start Robustness Test Script ---")

# 1. 正确的初始化命令
print("Setting up model new and creating a ball...")
itasca.command("model new")
itasca.command("model domain extent -10 10")
itasca.command("ball create radius 0.1 pos 0 0 0")
print("Initialization successful.")

# 2. 故意植入 PFC 引擎语法错误（暂时注释掉，测试 Python 错误）
# print("Triggering intentional PFC Command Syntax Error...")
# 'model gravity' 只接受一个数字或一个向量，此处给出的是一个无效字符串
# itasca.command("model gravity ERROR_STRING_9.81")

# 3. 测试 Python 运行时错误（除零错误）
print("Triggering intentional Python runtime error (division by zero)...")
result = 1 / 0

# 4. 期望错误会终止脚本执行，以下行不应被打印
print("--- FAILURE: Script executed past the critical error line. ---")
