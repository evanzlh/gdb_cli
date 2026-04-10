// simulation.cpp - GDB CLI 测试目标程序
// 编译: g++ -g -O0 -o simulation simulation.cpp

#include <iostream>
#include <chrono>
#include <thread>
#include <string>

// 状态机
enum class State {
    INIT,
    RUNNING,
    PROCESSING,
    COMPLETE
};

// 模拟数据结构
struct Data {
    int iteration;
    int total_processed;
    int stage1_result;
    int stage2_result;
    State state;
};

// 第一阶段计算
int compute_stage1(Data& data) {
    data.state = State::PROCESSING;
    int result = data.iteration * 2 + 10;
    data.stage1_result = result;
    return result;
}

// 第二阶段计算
int compute_stage2(Data& data) {
    int result = data.stage1_result * 3 - 5;
    data.stage2_result = result;
    return result;
}

// 打印状态
void print_status(int iteration, const Data& data) {
    std::string state_str;
    switch (data.state) {
        case State::INIT: state_str = "INIT"; break;
        case State::RUNNING: state_str = "RUNNING"; break;
        case State::PROCESSING: state_str = "PROCESSING"; break;
        case State::COMPLETE: state_str = "COMPLETE"; break;
    }

    // 每 10 次迭代打印详细状态
    if (iteration % 10 == 0) {
        std::cout << "[迭代 " << iteration << "] "
                  << "状态: " << state_str
                  << ", 已处理: " << data.total_processed
                  << ", 阶段1结果: " << data.stage1_result
                  << ", 阶段2结果: " << data.stage2_result
                  << std::endl;
    } else {
        std::cout << "." << std::flush;
    }
}

// 处理单次迭代
void process_iteration(int iteration, Data& data) {
    data.iteration = iteration;
    compute_stage1(data);
    compute_stage2(data);
    data.total_processed++;
    print_status(iteration, data);
}

// 运行模拟
void run_simulation(int seconds) {
    std::cout << "开始模拟，运行 " << seconds << " 秒..." << std::endl;

    Data data = {0, 0, 0, 0, State::INIT};
    data.state = State::RUNNING;

    int iteration = 0;
    auto start_time = std::chrono::steady_clock::now();

    while (std::chrono::duration_cast<std::chrono::seconds>(
               std::chrono::steady_clock::now() - start_time).count() < seconds) {

        process_iteration(iteration, data);
        iteration++;

        // 每次迭代间隔 100ms
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    data.state = State::COMPLETE;
    std::cout << std::endl << "模拟完成，共迭代 " << iteration
              << " 次，处理 " << data.total_processed << " 个数据" << std::endl;
}

int main(int argc, char* argv[]) {
    int seconds = 90;  // 默认运行 90 秒

    if (argc > 1) {
        seconds = std::stoi(argv[1]);
    }

    run_simulation(seconds);
    return 0;
}