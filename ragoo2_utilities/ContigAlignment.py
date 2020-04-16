#!/usr/bin/env python

import operator
from collections import defaultdict

from ragoo_utilities.utilities import summarize_planesweep


class ContigAlignment:
    """
    Description
    """

    def __init__(self, in_query_header, in_query_len, in_reference_headers, in_ref_lens, in_ref_starts, in_ref_ends, in_query_starts, in_query_ends, in_strands, in_aln_lens, in_mapqs):
        # Query info
        self.query_header = in_query_header
        self.query_len = in_query_len

        # Attributes describing alignments
        self._ref_headers = in_reference_headers
        self._ref_lens = in_ref_lens
        self._ref_starts = in_ref_starts
        self._ref_ends = in_ref_ends
        self._query_starts = in_query_starts
        self._query_ends = in_query_ends
        self._strands = in_strands
        self._aln_lens = in_aln_lens
        self._mapqs = in_mapqs

        # Check that the dimensions are valid
        all_lens = self._get_attr_lens()
        if not len(set(all_lens)) == 1:
            raise ValueError("The alignments are incomplete.")
        if not all_lens[0]:
            raise ValueError("ContigAlignment must contain at least one alignment.")

        # Attributes derived from alignments
        self.best_ref_header = None
        self.grouping_confidence = None
        self._get_best_ref_header()

        self.primary_alignment = None
        self._get_primary_alignment()

        self.orientation = self._strands[self.primary_alignment]
        self.orientation_confidence = None
        self._get_orientation_confidence()
        self.location_confidence = None
        self._get_location_confidence()

    def __str__(self):
        alns = []
        for i in range(len(self._ref_headers)):
            alns.append("\t".join([
                self.query_header,
                str(self.query_len),
                str(self._query_starts[i]),
                str(self._query_ends[i]),
                self._strands[i],
                self._ref_headers[i],
                str(self._ref_lens[i]),
                str(self._ref_starts[i]),
                str(self._ref_ends[i]),
                str(self._aln_lens[i]),
                str(self._mapqs[i])
            ]))
        return "\n".join(alns)

    def _get_attr_lens(self):
        all_lens = [
            len(self._ref_headers),
            len(self._ref_lens),
            len(self._ref_starts),
            len(self._ref_ends),
            len(self._query_starts),
            len(self._query_ends),
            len(self._strands),
            len(self._aln_lens),
            len(self._mapqs)
        ]
        return all_lens

    def _get_best_ref_header(self):
        """ From the alignments, determine the reference sequence that is the most covered by this query sequence. """
        # Get the set of all references chromosomes
        all_ref_headers = set(self._ref_headers)
        if len(all_ref_headers) == 1:
            self.best_ref_header = self._ref_headers[0]
            self.grouping_confidence = 1

        # Initialize coverage counts for each chromosome
        ranges = defaultdict(int)

        # Get all the alignment intervals for each reference sequence
        all_intervals = defaultdict(list)
        for i in range(len(self._ref_headers)):
            this_range = (self._ref_starts[i], self._ref_ends[i])
            this_seq = self._ref_headers[i]
            all_intervals[this_seq].append(this_range)

        # For each reference header, sort the intervals and get the union interval length.
        for i in all_intervals.keys():
            sorted_intervals = sorted(all_intervals[i], key=lambda tup: tup[0])
            max_end = -1
            for j in sorted_intervals:
                start_new_terr = max(j[0], max_end)
                ranges[i] += max(0, j[1] - start_new_terr)
                max_end = max(max_end, j[1])

        # I convert to a list and sort the ranges.items() in order to have ties broken in a deterministic way.
        max_seq = max(sorted(list(ranges.items())), key=operator.itemgetter(1))[0]
        self.best_ref_header = max_seq

        # Now get the confidence of this chromosome assignment
        # Equal to the max range over all ranges
        self.grouping_confidence = ranges[max_seq] / sum(ranges.values())

    def _get_primary_alignment(self):
        # Needs to be primary of the alignments to the best
        max_index = -1
        max_len = -1
        for i in self._get_best_ref_alns():
            this_len = self._aln_lens[i]
            if this_len > max_len:
                max_len = this_len
                max_index = i
        self.primary_alignment = max_index

    def _get_orientation_confidence(self):
        """ Get the orientation confidence score given these alignments for a given query sequence. """
        num = 0
        denom = 0
        for i in self._get_best_ref_alns():
            aln_len = self._aln_lens[i]
            if self._strands[i] == self.orientation:
                num += aln_len
            denom += aln_len
        self.orientation_confidence = num/denom

    def _get_location_confidence(self):
        """ Get the location confidence score given these alignments for a given query sequence. """
        best_ref_alns = self._get_best_ref_alns()

        # Get all the alignment reference intervals for alignments to the best reference sequence
        aln_intervals = []
        all_positions = []
        for i in best_ref_alns:
            aln_intervals.append((self._ref_starts[i], self._ref_ends[i]))
            all_positions.append(self._ref_starts[i])
            all_positions.append(self._ref_ends[i])

        # The denominator is the max - min alignment positions
        denom = max(all_positions) - min(all_positions)

        # The numerator is the coverage
        num = 0
        sorted_intervals = sorted(aln_intervals, key=lambda tup: tup[0])
        max_end = -1
        for j in sorted_intervals:
            start_new_terr = max(j[0], max_end)
            num += max(0, j[1] - start_new_terr)
            max_end = max(max_end, j[1])

        self.location_confidence = num/denom

    def _get_best_ref_alns(self):
        return [i for i in range(len(self._ref_headers)) if self._ref_headers[i] == self.best_ref_header]

    def _update_alns(self, hits):
        """ Order the alignments according to 'hits', an ordered list of indices. Return a new instance of the class. """
        if hits:
            return ContigAlignment(
                self.query_header,
                self.query_len,
                [self._ref_headers[i] for i in hits],
                [self._ref_lens[i] for i in hits],
                [self._ref_starts[i] for i in hits],
                [self._ref_ends[i] for i in hits],
                [self._query_starts[i] for i in hits],
                [self._query_ends[i] for i in hits],
                [self._strands[i] for i in hits],
                [self._aln_lens[i] for i in hits],
                [self._mapqs[i] for i in hits]
            )
        else:
            return None

    def _rearrange_alns(self, hits):
        """ Order the alignments according to 'hits', an ordered list of indices. """
        if len(hits) != len(self._ref_headers):
            raise ValueError("Can only shuffle alignments. To update, use '_update_alns()'")

        self._ref_headers = [self._ref_headers[i] for i in hits]
        self._ref_lens = [self._ref_lens[i] for i in hits]
        self._ref_starts = [self._ref_starts[i] for i in hits]
        self._ref_ends = [self._ref_ends[i] for i in hits]
        self._query_starts = [self._query_starts[i] for i in hits]
        self._query_ends = [self._query_ends[i] for i in hits]
        self._strands = [self._strands[i] for i in hits]
        self._aln_lens = [self._aln_lens[i] for i in hits]
        self._mapqs = [self._mapqs[i] for i in hits]

    def _sort_by_ref(self):
        ref_pos = []
        for i in range(len(self._ref_headers)):
            ref_pos.append((self._ref_headers[i], self._ref_starts[i], self._ref_ends[i], i))
        hits = [i[3] for i in sorted(ref_pos)]

        self._rearrange_alns(hits)

    def _sort_by_query(self):
        q_pos = []
        for i in range(len(self._ref_headers)):
            q_pos.append((self._query_starts[i], self._query_ends[i], i))
        hits = [i[2] for i in sorted(q_pos)]

        self._rearrange_alns(hits)

    def add_alignment(self, in_reference_header, in_ref_len, in_ref_start, in_ref_end, in_query_start, in_query_end, in_strand, in_aln_len, in_mapq):
        """ Add an alignment for this query. """
        return ContigAlignment(
            self.query_header,
            self.query_len,
            self._ref_headers + [in_reference_header],
            self._ref_lens + [in_ref_len],
            self._ref_starts + [in_ref_start],
            self._ref_ends + [in_ref_end],
            self._query_starts + [in_query_start],
            self._query_ends + [in_query_end],
            self._strands + [in_strand],
            self._aln_lens + [in_aln_len],
            self._mapqs + [in_mapq]
        )

    def filter_lengths(self, l):
        """ Remove alignments shorter than l. """
        hits = [i for i in range(len(self._ref_headers)) if self._aln_lens[i] >= l]
        return self._update_alns(hits)

    def filter_mapq(self, q):
        """ Remove alignments with mapq < q. """
        hits = [i for i in range(len(self._ref_headers)) if self._mapqs[i] >= q]
        return self._update_alns(hits)

    def unique_anchor_filter(self, l):
        """
        Unique anchor filter the alignments. l is the minimum unique alignment length.

        The contents of this method are either influenced by or directly copied from "Assemblytics_uniq_anchor.py"
        written by Maria Nattestad. The original script can be found here:

        https://github.com/MariaNattestad/Assemblytics

        And the publication associated with Maria's work is here:

        Nattestad, Maria, and Michael C. Schatz. "Assemblytics: a
        web analytics tool for the detection of variants from an
        assembly." Bioinformatics 32.19 (2016): 3021-3023.
        """
        lines_by_query = []
        for i, j in zip(self._query_starts, self._query_ends):
            lines_by_query.append((i, j))

        hits = summarize_planesweep(lines_by_query, l)
        return self._update_alns(hits)

    def get_best_ref_pos(self):
        """ Return the ref start and ref end for the primary alignment. """
        return self._ref_starts[self.primary_alignment], self._ref_ends[self.primary_alignment]

    def get_best_ref_flanks(self):
        """
        With respect to the "best" reference sequence, return the lowest and highest alignment positions
        :return: lowest position, highest position
        """
        ref_pos = []
        for i in self._get_best_ref_alns():
            ref_pos.append(self._ref_starts[i])
            ref_pos.append(self._ref_ends[i])

        return min(ref_pos), max(ref_pos)

    def filter_query_contained(self):
        """
        Remove alignments that are contained (w.r.t the query) by other alignments.
        This does not consider alignments contained by chains of alignments.
        Consider merging first (merge_alns) to account for that.
        """
        cidx = set()
        for i in range(len(self._ref_headers)):
            for j in range(len(self._ref_headers)):
                # Check if j is contained by i
                if i == j:
                    continue
                if self._query_starts[i] <= self._query_starts[j] and self._query_ends[i] >= self._query_ends[j]:
                    cidx.add(j)

        hits = [i for i in range(len(self._ref_headers)) if i not in cidx]
        return self._update_alns(hits)

    def merge_alns(self, merge_dist=100000):
        """
        Merge adjacent alignments that have the same reference sequence, the same orientation, and are less than
        merge_dist away from each other.
        """
        # Sort the alignments
        self._sort_by_ref()

        # Make a copy of the alignment info
        ref_headers = self._ref_headers
        ref_lens = self._ref_lens
        ref_starts = self._ref_starts
        ref_ends = self._ref_ends
        query_starts = self._query_starts
        query_ends = self._query_ends
        strands = self._strands
        aln_lens = self._aln_lens
        mapqs = self._mapqs

        # Keep track of which alignments we are comparing
        i = 0
        j = 1
        while j < len(ref_headers):
            if all([
                        ref_headers[i] == ref_headers[j],
                        strands[i] == strands[j],
                        ref_starts[j] - ref_ends[i] <= merge_dist
            ]):
                # Merge the alignments in place of the first alignment
                ref_starts[i] = min(ref_starts[i], ref_starts[j])
                ref_ends[i] = max(ref_ends[i], ref_ends[j])
                query_starts[i] = min(query_starts[i], query_starts[j])
                query_ends[i] = max(query_ends[i], query_ends[j])

                aln_lens[i] = ref_ends[i] - ref_starts[i]
                mapqs[i] = (mapqs[i] + mapqs[j]) // 2

                # Remove the redundant alignment
                query_starts.pop(j)
                query_ends.pop(j)
                strands.pop(j)
                ref_headers.pop(j)
                ref_lens.pop(j)
                ref_starts.pop(j)
                ref_ends.pop(j)
                aln_lens.pop(j)
                mapqs.pop(j)
            else:
                i += 1
                j += 1

        # Make a new object with the merged data
        x = ContigAlignment(
            self.query_header,
            self.query_len,
            ref_headers,
            ref_lens,
            ref_starts,
            ref_ends,
            query_starts,
            query_ends,
            strands,
            aln_lens,
            mapqs
        )

        # remove contained alignments.
        return x.filter_query_contained()

    def get_break_candidates(self, min_dist=5000):
        """
        Return coordinates of the query sequence between consecutive alignments.
        Consider merging alignments first (merge_alns)
        :return: Two lists of coordinates. One where consecutive alignments aligned to the
        same reference (intra) and one where the consecutive alignments aligned to different
        references (inter).
        """
        self._sort_by_query()
        intra_candidates = []
        inter_candiats = []

        # If there are more than two alignments, iterate through all but the first.
        for i in range(1, len(self._ref_headers)):
            if min_dist < self._query_starts[i] < (self.query_len - 5000):
                if self._ref_headers[i] == self._ref_headers[i-1]:
                    intra_candidates.append(self._query_starts[i])
                else:
                    inter_candiats.append(self._query_starts[i])

        return intra_candidates, inter_candiats
