DATADIR ?= /gis/data
MAPCREATORDIR ?= /gis/mapcreator
PLANETFILE ?= $(DATADIR)/planet-latest.o5m
TIMEOUT ?= 2h
LOGLEVEL ?= INFO

define remove-file
[ -f $1 ] && rm $1 || true
endef

define remove-dir
[ -d $1 ] && rm -rf $1 || true
endef

define run-in-dir
[ -d $1 ] && cd $1 && $2
endef

$(PLANETFILE) :
	echo "Planet file does not exist! Exiting..."
	false

$(DATADIR)/%.o5m : $(PLANETFILE)
	$(call remove-file,$@)
	osmfilter $< --parameter-file=$(MAPCREATORDIR)/filters/$*.filter >$@

%.mtiles: $(PLANETFILE)
	/usr/bin/timeout --kill-after=60s $(TIMEOUT) $(MAPCREATORDIR)/mapcreator.py -l $(LOGLEVEL) --area "$*"

basemap : % : $(DATADIR)/%.o5m
	$(call remove-file,$(DATADIR)/$*.mtiles)
	$(MAPCREATORDIR)/mapwrite.py -l $(LOGLEVEL) -k -f -p $(DATADIR) -1 -1

stubmap : % : $(DATADIR)/%.o5m
	$(call remove-file,$(DATADIR)/$*.mtiles)
	$(MAPCREATORDIR)/mapwrite.py -l $(LOGLEVEL) -k -f -p $(DATADIR) -2 -2

boundaries : % : $(DATADIR)/%.o5m
	$(MAPCREATORDIR)/boundaries.py -l $(LOGLEVEL) -p $(DATADIR)

routes : % : $(DATADIR)/%.o5m
	$(MAPCREATORDIR)/routes.py -l $(LOGLEVEL) -p $(DATADIR)

maps : $(PLANETFILE)
	@while [ ! -f $(MAPCREATORDIR)/stop ] ; do \
		/usr/bin/timeout --kill-after=60s $(TIMEOUT) $(MAPCREATORDIR)/mapcreator.py -l $(LOGLEVEL); \
	done; \
	true

world : $(PLANETFILE)
	@y=0 ; while [ $$y -le 127 -a ! -f $(MAPCREATORDIR)/stop -a ! -f $(MAPCREATORDIR)/pause ] ; do \
		x=0 ; while [ $$x -le 127 -a ! -f $(MAPCREATORDIR)/stop ] ; do \
			$(MAKE) $$x-$$y.mtiles ; \
			((x = x + 1)) ; \
		done ; \
		((y = y + 1)) ; \
	done; \
	true

publish :
	rsync -vru --exclude='nativeindex' --exclude='lost+found' --exclude='index' --delete-after /gis/maps/* tanya.newf.ru:/gis/maps/
	ssh tanya.newf.ru /gis/mapcreator/index.py

downloads :
	ssh tanya.newf.ru pg_dump -c -t map_downloads gis > /tmp/downloads.sql
	cat /tmp/downloads.sql | psql gis

update : $(PLANETFILE)
	$(call remove-file,$(DATADIR)/planet-updated.o5m)
	osmupdate -v --day $< $(DATADIR)/planet-updated.o5m
	mv $(DATADIR)/planet-updated.o5m $<

water :
	$(call remove-file,$(DATADIR)/water-polygons-split-3857.zip)
	$(call remove-file,$(DATADIR)/water-polygons-generalized-3857.zip)
	$(call remove-dir,$(DATADIR)/water-polygons-split-3857)
	$(call remove-dir,$(DATADIR)/water-polygons-generalized-3857)
	wget http://data.openstreetmapdata.com/water-polygons-split-3857.zip -P $(DATADIR)
	wget http://data.openstreetmapdata.com/water-polygons-generalized-3857.zip -P $(DATADIR)
	unzip $(DATADIR)/water-polygons-split-3857.zip -d $(DATADIR)
	unzip $(DATADIR)/water-polygons-generalized-3857.zip -d $(DATADIR)
	$(call run-in-dir,$(DATADIR),$(MAPCREATORDIR)/setup/water2pgsql.sh | psql gis)

.PHONY: basemap stubmap boundaries maps world publish downloads update water
