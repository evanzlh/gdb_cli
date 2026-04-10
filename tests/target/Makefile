# Makefile for simulation test program

CXX = g++
CXXFLAGS = -g -O0 -std=c++11

TARGET = simulation
SRC = simulation.cpp

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SRC)

clean:
	rm -f $(TARGET)