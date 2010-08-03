#!/usr/bin/perl -w
#
# pooldebclean.pl {directory} {dist}
#
# Scan pool and dist directories and snapshots.
# Delete any deb that is not in a dist.
#
# Copyright 2010 Google Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Author: Drake Diedrich <dld@google.com>

use Getopt::Long;
use Pod::Usage;
use DirHandle;
use File::Path qw(make_path remove_tree);

#
# Return a list of files of all the Packages files
#
sub packages_files($);
sub packages_files($) {
  my ($dir) = @_;
  my (@packages);
  my $dh = new DirHandle $dir;
  foreach (my $de = $dh->read) {
    next if ($de eq '.' || $de eq '..');
    my $path = "$dir/$de";
    if (-d $path) {
      push @packages, packages_files($path);
    } elsif (-f $path && $de eq 'Packages') {
      push(@packages,$path);
    }
  }
  @packages;
}

#
# Parse an open filehandle that is a Packages file for the complete
# list of .debs that are indexed in a repository.
#
sub parse_packages($$) {
  my ($fh,$packages) = @_;
  while (my $line = $fh->getline) {
    if ($line =~ /^Filename:\s*(\S+)\s*$/) {
      $packages->{$1}++;
    }
  }
}


sub purge_pool($$$$);
sub purge_pool($$$$) {
  my ($dir,$path,$packages,$unlink) = @_;

  my $dh = new DirHandle $dir;
  foreach (my $de = $dh->read) {
    my $fullpath = "$path/$de";
    next if $de eq '.' || $de eq '..';
    if (-d $fullpath) {
      purge_pool("$dir/$de","$path/$de",$packages,$unlink);
    } elsif (-f $fullpath) {
      if ($de =~ /\.deb$/) {
	if (!defined $packages->{"$dir/$de"}) {
	  &{$unlink}($fullpath);
	}
      }
    }
  }
}

sub pooldebclean($$) {
  my ($repository,$options) = @_;
  my (%packages);

  if (! -d $repository) {
    return ["$repository/ does not exist", 2];
  }
  if (! -d "$repository/dists") {
    return ["$repository/dists/ does not exist", 2];
  }
  if (! -d "$repository/pool") {
    return ["$repository/pool/ does not exist",2];
  }

  foreach my $package (@{&packages_files("$repository/dists")}) {
    my $packagefh = new FileHandle $package;
    parse_packages($packagefh,\%packages);
  }

  purge_pool("$repository/pool", "pool", \%packages, sub {unlink @_;} );


  [undef, 0];
}


# main()
#
# Parse options, print usage, and return with exit codes.
#
sub main {
  my %options;

  my $result = GetOptions(\%options,
             'help|?',
             'man')
    or pod2usage(2);

  pod2usage(1) if $options{'help'};
  pod2usage(-verbose => 2) if $options{'man'};

  if (@ARGV != 1) {
    pod2usage("$0: Repository directory required.\n");
  }

  my ($inputdir) = @ARGV;

  my ($rcmsg,$rc) = pooldebclean($inputdir, \%options);
  print STDERR $rcmsg;
  $rc;
}

if (!caller()) {
  main();
} else {
  return 1;
}


__END__

=head1 NAME

debmarshal_pooldebclean - remove unused .deb pool files from a repository


=head1 SYNOPSIS

debmarshal_pooldebclean {repository directory}

 Options:
   -help            brief help message
   -man             full documentation

=head1 OPTIONS

=over 8

=item B<-help>

Print a brief help message and exits.

=item B<-man>

Prints the manual page and exits.

=back

=head1 DESCRIPTION

B<debmarshal_pooldebclean> will delete all the unused .debs in a repository
pool, including debmarshal snapshot and regular Debian repositories.

=cut
