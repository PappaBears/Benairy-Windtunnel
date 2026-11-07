# Host build of the controller core and its unit tests (no Arduino needed).
CXX ?= g++
CXXFLAGS ?= -std=c++17 -O1 -g -Wall -Wextra -Werror
all: build/test_controller
build/test_controller: ../src/controller.cpp ../src/controller.h ../src/hal.h test_main.cpp sim_hal.h
	@mkdir -p build
	$(CXX) $(CXXFLAGS) ../src/controller.cpp test_main.cpp -o $@
test: build/test_controller
	./build/test_controller
clean:
	rm -rf build
