import time
import os
import argparse
import csv
import re
import subprocess
import tempfile
import math
from tqdm import tqdm


parser = argparse.ArgumentParser()
parser.add_argument("-o", "--output",
                    help='Output file path.')
parser.add_argument("-r", "--repeat", type=int,
                    help="Repeat time per benchmark.")
parser.add_argument("-m", "--max_thread", type=int,
                    help="Maxium numbers of thread usage. Must be even number.")
parser.add_argument("-perf", action='store_true',
                    help="Use perf probe on each benchmarks")
parser.add_argument("-sim", action='store_true',
                    help="Choose to run simulation or not, default is not.")
parser.add_argument("-debug", action='store_true',
                    help="To print debug information or not.")
parser.add_argument("-s", "--specific",
                    default="all",
                    help="Only test the specific benchmark (default: all).")
parser.add_argument("-e", "--error", action="store_true",
                    help="Reexecute the 0 execution benchmarks and print error message")

args = parser.parse_args()

dic = ['bayes', 'genome', 'intruder', 'kmeans', 'labyrinth', 'ssca2', 'vacation', 'yada']
cmds_index = ['bayes', 'genome', 'intruder', 'kmeans_high', 'kmeans_low', 'labyrinth', 'ssca2', 'vacation_high', 
             'vacation_low', 'yada']
# Check all the arguments are set.
assert args.output != None, "Output file path should be added!"
assert args.repeat != None, "Repeat time lost!"
assert args.max_thread != None, "Need to allocate max thread number!"
assert (args.max_thread & (args.max_thread - 1) == 0 and args.max_thread != 0), "Max thread number should be power of 2!"
if (args.specific != "all"): 
    assert args.specific in cmds_index, "Specific benchmark name error! [bayes, genome, intruder, kmeans_high, kmeans_low, labyrinth, ssca2, vacation_high, vacation_low, ssca2]"
    specific_bench = args.specific



ROOT = os.path.abspath(os.getcwd())


"""
    bayes: -t: thread
    genome: -t: thread
    intruder: -t: thread
    kmeans: -p: thread
    labyrinth: no thread parameter
    ssca2: -t: thread
    vacation: no thread parameter
    yada: -t: thread
"""


# Non-simulated commands
cmds = {
    "bayes": "./bayes.stm -v32 -r4096 -n10 -p40 -i2 -e8 -s1 -t",
    "genome": "./genome.stm -g16384 -s64 -n16777216 -t",
    "intruder": "./intruder.stm -a10 -l128 -n262144 -s1 -t",
    "kmeans_high": "./kmeans.stm -m15 -n15 -t0.00001 -i inputs/random-n65536-d32-c16.txt -p",
    "kmeans_low": "./kmeans.stm -m40 -n40 -t0.00001 -i inputs/random-n65536-d32-c16.txt -p",
    "labyrinth": "./labyrinth.stm -i inputs/random-x512-y512-z7-n512.txt -t",
    "ssca2": "./ssca2.stm -s20 -i1.0 -u1.0 -l3 -p3 -t",
    "vacation_high": "./vacation.stm -n4 -q60 -u90 -r1048576 -t4194304 -c",
    "vacation_low": "./vacation.stm -n2 -q90 -u98 -r1048576 -t4194304 -c",
    "yada": "./yada.stm -a15 -i inputs/ttimeu1000000.2 -t"
}

cmds_sim = {
    "bayes": "./bayes.stm -v32 -r1024 -n2 -p20 -s0 -i2 -e2 -t",
    "genome": "./genome.stm -g256 -s16 -n16384 -t",
    "intruder": "./intruder.stm -a10 -l4 -n2038 -s1 -t",
    "kmeans_high": "./kmeans.stm -m15 -n15 -t0.05 -i inputs/random-n2048-d16-c16.txt -p",
    "kmeans_low": "./kmeans.stm -m40 m40 -n40 -t0.05 -i inputs/random-n2048-d16-c16.txt -p",
    "labyrinth": "./labyrinth.stm -i inputs/random-x32-y32-z3-n96.txt -t",
    "ssca2": "./ssca2.stm -s13 -i1.0 -u1.0 -l3 -p3 -t",
    "vacation_high": "./vacation.stm -n4 -q60 -u90 -r16384 -t4096 -c",
    "vacation_low": "./vacation.stm -n2 -q90 -u98 -r16384 -t4096 -c",
    "yada": "./yada.stm -a20 -i inputs/633.2 -t"
}

#perf_cmd_prefix = 'sudo perf '

# Re-compile each benchmarks
for ele in dic:
    print('cd '+ele)
    #os.system('cd '+ele)
    os.chdir(ele)
    os.system('make -f Makefile.stm clean')
    os.system('make -f Makefile.stm')
    os.chdir(ROOT)

# Insert probe to each benchmarks if perf flag is open
if args.perf:
    os.system("perf probe --del=*") # Delete previous probe
    for ele in dic:
        os.chdir(ele)
        os.system("sudo perf probe -x ./"+ele+".stm "+ele+"_stm_start_entry=stm_start")
        os.system("sudo perf probe -x ./"+ele+".stm "+ele+"_stm_commit_entry=stm_commit")
        os.system("sudo perf probe -x ./"+ele+".stm "+ele+"_stm_commit_exit=stm_commit%return")
        os.system("sudo perf probe -x ./"+ele+".stm "+ele+"_stm_abort_entry=stm_abort")
        os.system("sudo perf probe -x ./"+ele+".stm "+ele+"_stm_rollback_entry=stm_rollback")
        os.system("sudo perf probe -x ./"+ele+".stm "+ele+"_stm_rollback_exit=stm_rollback%return")
        os.chdir(ROOT)

    # TODO: Executing with perf state
    


# If we choose to run in simulator
if args.sim:
    cmds = cmds_sim

"""
for i in range(times):
    for bench in cmds:
"""
def execute_and_count(cmd, index):
    #print("cmd: ", cmd)

    cmd_list = cmd.split(' ')
    
    # Hide output terminal and capture execution time with output
    with tempfile.TemporaryFile() as tempf: 
        # Execute benchmark 
        proc = subprocess.Popen(cmd_list, stdout=tempf, stderr=tempf)
        proc.wait()
        tempf.seek(0)
        exe_time = [0]
        match_lines = []
        output_tmp = []
        # Find time
        for line in tempf.readlines():
            # Print original output if debug flag
            if args.debug:
                print(str(line))
            if args.error:
                output_tmp.append(line)
            time = re.search(r'(?i)time', str(line))
            if time is not None:
                match_lines.append(str(line))
                exe_time.append(float(re.findall(r"[-+]?\d*\.\d+|\d+", str(line))[0]))
                # Exception handle for ssca2, overlap the order time
                if re.search(r'Time taken for all is', str(line)) is not None:
                    exe_time = re.findall(r"[-+]?\d*\.\d+|\d+", str(line))
                #print(line)
        exe_sum = sum([float(x) for x in exe_time])
        
        # Exclude 0 execution time and restart
        if args.error:
            # If find the 0 execution time
            if exe_sum == 0:
                # Print error message
                for ele in output_tmp:
                    print(ele)
                # Re-execute this benchmarks
                execute_and_count(cmd, index)
                # End this function call
                return
        # Debug mode: reveal original executed result & captured time
        if args.debug:
            print("cmd: ", cmd)
            print("match line: ", match_lines )
            print("exe_time: ", exe_time)
            print("exe_sum: ", exe_sum)
        print("-----------------------------------------------------------------------")
        
    # Record the execution time1
    exe_time_dic[index].append(exe_sum)
 



max_thread_num = args.max_thread
times = args.repeat


# exe_time_dic = { 'kmeans': [], ... }
exe_time_dic = {}

for bench in cmds_index:
    exe_time_dic[bench] = []

exe_time_dic['kmeans_high'] = []
exe_time_dic['kmeans_low'] = []
exe_time_dic['vacation_high'] = []
exe_time_dic['vacation_low'] = []

high_flag = 0
thread_batch_times = (2**i for i in range(0, int(math.log(max_thread_num, 2))+1))

# Progress bar
tqdm_times = times*len(cmds_index)*math.log(max_thread_num, 2)
with tqdm(total=tqdm_times) as pbar:
    for thread_num in thread_batch_times:
        for i in range(times):
            for bench in dic:
                os.chdir(bench)
                index = bench

                # Special case handling: kmeans & vacaction
                if bench == 'kmeans' or bench == 'vacation':
                    high_cmd = cmds[index + '_high']
                    low_cmd = cmds[index + '_low']
                    high_cmd += str(thread_num)
                    low_cmd += str(thread_num)

                    # Specific bench feature
                    if (specific_bench != "all" and high_cmd != specific_bench and low_cmd != specific_bench):
                        os.chdir(ROOT)
                        # Skip the execution of kmeans and vaction
                        continue

                    execute_and_count(high_cmd, index + '_high')
                    execute_and_count(low_cmd, index + '_low')
                    os.chdir(ROOT)
                    continue

                # Specific bench feature
                if (specific_bench != "all" and index != specific_bench):
                    # Skip the execution of non-specific benchmarks & jump to ROOT
                    os.chdir(ROOT)
                    continue

                cmd = cmds[index]
                cmd += str(thread_num)
                
                execute_and_count(cmd, index)
                pbar.update(1) # update progress bar    
                os.chdir(ROOT)

# Record to file and caculate averages
avg_list = []
with open(args.output, 'w') as f:
    count = 0
    exe_sum = 0
    f.write("Times: " + str(times) + "\n")
    for key, val in exe_time_dic.items():
        f.write("Benchmarks: "+ str(key) + "\n")
        for ele in val:
            f.write(str(ele) + ", ") # Record each execution time
            exe_sum += ele
            if count == (times-1):
                avg = exe_sum / times
                avg_list.append(avg) # Append average time to list
                count = 0
                exe_sum = 0
            else:
                count += 1
        f.write("\n")
        f.write("Average: ")
        for avg in avg_list:
            f.write(str(avg)+ ',')
        f.write("\n")
        avg_list = []


if __name__ == '__main__':
    print("Hi")
