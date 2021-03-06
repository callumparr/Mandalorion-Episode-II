#!/usr/bin/env python3
# Christopher Vollmers
# Roger Volden

import os
import sys
import numpy as np

path = sys.argv[2]
content_file = sys.argv[1]
upstream_buffer = int(sys.argv[4])
downstream_buffer = int(sys.argv[3])

minimum_read_count = 1

def find_peaks(starts, ends):
    start_peaks = {}
    end_peaks = {}
    for position in sorted(starts):
        if list(starts).count(position) >= minimum_read_count:
            if not start_peaks.get(position):
                for shift in np.arange(-upstream_buffer, downstream_buffer):
                    start_peaks[position+shift] = position
    for position in sorted(ends, reverse=True):
        if list(ends).count(position) >= minimum_read_count:
            if not end_peaks.get(position):
                for shift in np.arange(-downstream_buffer, upstream_buffer, 1):
                    end_peaks[position+shift] = position
    return start_peaks, end_peaks

def collect_splice_events(path):
    splice_dict = {}
    for line in open(path + '/SS.bed'):
        a = line.strip().split('\t')
        chromosome = a[0]
        if not splice_dict.get(chromosome):
            splice_dict[chromosome] = {}
        splice_left =int(a[1])
        splice_right = int(a[2])
        for base in np.arange(splice_left, splice_right+1):
             splice_dict[chromosome][base] = a[3].split('_')[0]
    return splice_dict

def sort_reads_into_splice_junctions(content_file, splice_dict,
                                     fasta_file, infile):
    start_end_dict = {}
    readDict = {}
    tempSeqs, headers, sequences = [], [], []
    for line in open(fasta_file):
        line = line.rstrip()
        if not line:
            continue
        if line.startswith('>'):
            headers.append(line.split()[0][1:])
        # covers the case where the file ends while reading sequences
        if line.startswith('>'):
            sequences.append(''.join(tempSeqs).upper())
            tempSeqs = []
        else:
            tempSeqs.append(line)
    # fasta_file.close()
    sequences.append(''.join(tempSeqs).upper())
    sequences = sequences[1:]
    for i in range(len(headers)):
        readDict[headers[i].split('_')[0]] = [headers[i], sequences[i]]
    read_dict = readDict

    print(len(read_dict))

    for line in open(infile):
        a = line.strip().split('\t')
        chromosome, read_direction = a[13], a[8]
        name = a[9].split('_')[0]
        read_direction = '+' ### Ignores read direction
        start, end = int(a[15]), int(a[16])

        if read_direction == '+':
            left_extra, right_extra = int(a[11]), int(a[10]) - int(a[12])
        if read_direction == '-':
            right_extra, left_extra = int(a[11]), int(a[10]) - int(a[12])

        failed = False
        identity = chromosome + '_'

        blocksizes = a[18].split(',')[:-1]
        blockstarts = a[20].split(',')[:-1]
        readstarts = a[19].split(',')[:-1]

        for x in range(0, len(blocksizes)-1):
                blockstart = int(blockstarts[x])
                blocksize = int(blocksizes[x])
                left_splice = blockstart + blocksize
                right_splice = int(blockstarts[x+1])
                if right_splice - left_splice > 50:
                    try:
                        left_splice_site = splice_dict[chromosome][left_splice]
                    except:
                        failed = True
                    try:
                        right_splice_site = splice_dict[chromosome][right_splice]
                        
                    except:
                        failed = True
                    if not failed:
                        identity += str(left_splice_site) + '-' \
                                    + str(right_splice_site) + '~'
                    if '5r133331' in identity:
                        print(identity,failed)

        if not failed:
            if not start_end_dict.get(identity):
                start_end_dict[identity] = []
            start_end_dict[identity].append((start, end,
                                             '>' + read_dict[name][0] + '\n'
                                             + read_dict[name][1] + '\n',
                                             left_extra,
                                             right_extra,
                                             read_direction))
    return start_end_dict

def define_start_end_sites(start_end_dict, individual_path, subreads):
    left_extras, right_extras = {}, {}
    file_set = set()
    isoform_counter, isoform_dict = 0, {}

    for identity in start_end_dict:
        if '5r133331' in identity:
            print(identity)       

        # if 'chr16' in identity:
        #     print(identity)
        positions = np.array(start_end_dict[identity])
        starts = np.array(positions[:,0], dtype=int)
        ends = np.array(positions[:,1], dtype=int)
        if '5r133331' in identity:
            print(identity,starts,ends) 


        start_dict, end_dict =find_peaks(starts, ends)
        if '5r133331' in identity:
            print(identity,start_dict,end_dict) 


        matched_positions = []
        combination_counts = {}
        left_extras[identity], right_extras[identity] = {}, {}

        for start, end, read, left_extra, right_extra, read_direction in positions:
            try:
                left = start_dict[int(start)]
                right = end_dict[int(end)]
                if not left_extras[identity].get((left, right)):
                    left_extras[identity][(left,right)] = []
                    right_extras[identity][(left,right)] = []

                left_extras[identity][(left, right)].append(int(left_extra))
                right_extras[identity][(left, right)].append(int(right_extra))

                if not combination_counts.get((left, right)):
                    combination_counts[(left, right)] = 1
                else:
                    combination_counts[(left, right)] += 1
                matched_positions.append((left, right, read, read_direction))
            except:
                pass
        for left, right, read, read_direction in matched_positions:
            medianLeft = np.median(left_extras[identity][(left, right)])
            medianRight = np.median(right_extras[identity][(left, right)])
            new_identity = identity + '_' + str(left) \
                           + '_' + str(right) + '_' \
                           + str(round(medianLeft, 2)) \
                           + '_' + str(round(medianRight, 2))
            if not isoform_dict.get(new_identity):
                isoform_counter += 1
                isoform_dict[new_identity] = isoform_counter


            filename='Isoform'+str(isoform_dict[new_identity])

            out_reads_fasta = open(individual_path + '/parsed_reads/'
                                   + filename + '.fasta', 'a')
            out_reads_subreads = open(individual_path + '/parsed_reads/'
                                      + filename + '_subreads.fastq', 'a')
            out_reads_fasta.write(read)
            out_reads_fasta.close()

            file_set.add(individual_path + '/parsed_reads/' + filename
                         + '.fasta' + '\t' + individual_path
                         + '/parsed_reads/' + filename + '_subreads.fastq'
                         + '\t' + new_identity + '\n')
            read = read.split('\n')[0][1:]
            subread_list = subreads[read]
            for subread, sequence, qual in subread_list:
                out_reads_subreads.write(subread + '\n' + sequence
                                         + '\n+\n' + qual +'\n')
            out_reads_subreads.close()


    out = open(individual_path + 'isoform_list', 'w')
    for item in file_set:
        out.write(item)
    out.close()

def read_subreads(seq_file, infile):
    read_seq = {}
    length = 0
    for line2 in open(seq_file):
        length += 1
    seq_file_open = open(seq_file,'r')
    counter = 0
    for line in open(infile):
        name = line.strip().split('\t')[9].split('_')[0]
        read_seq[name] = []

    while counter < length:
        name = seq_file_open.readline().strip()
        seq = seq_file_open.readline().strip()
        plus = seq_file_open.readline().strip()
        qual = seq_file_open.readline().strip()
        root_name = name[1:].split('_')[0]
        try:
            read_seq[root_name].append((name, seq, qual))
        except:
            pass
        counter += 4
    return read_seq

def main():
    for line in open(content_file):
      b = line.strip().split('\t')
      print(b)
      infile = b[0]
      fasta_file = b[1]
      individual_path = b[2]
      subreads_file = b[3]
      os.system('mkdir ' + individual_path + '/parsed_reads')
      os.system('rm ' + individual_path + '/parsed_reads/*')
      subreads = read_subreads(subreads_file, infile)
      splice_dict = splice_dict = collect_splice_events(path)
      start_end_dict = sort_reads_into_splice_junctions(content_file, splice_dict,
                                                        fasta_file, infile)
      define_start_end_sites(start_end_dict, individual_path, subreads)

if __name__ == '__main__':
    main()
