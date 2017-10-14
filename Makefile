DATADIR ?= /gis/data
MAPCREATORDIR ?= /gis/mapcreator
PLANETFILE ?= $(DATADIR)/planet-171012.o5m
TIMEOUT ?= 2h
LOGLEVEL ?= INFO

define remove-file
[ -f $1 ] && rm $1 || true
endef

$(PLANETFILE) :
	echo "Planet file does not exist! Exiting..."
	false

$(DATADIR)/%.o5m : $(PLANETFILE)
	$(call remove-file,$@)
	osmfilter $< --parameter-file=$(MAPCREATORDIR)/filters/basemap.filter >$@

%.mtiles: $(PLANETFILE)
	/usr/bin/timeout --kill-after=60s $(TIMEOUT) $(MAPCREATORDIR)/mapcreator.py -l $(LOGLEVEL) --area "$*"

basemap : % : $(DATADIR)/%.o5m
	$(call remove-file,$(DATADIR)/$*.mtiles)
	$(MAPCREATORDIR)/mapwrite.py -l $(LOGLEVEL) -k -f -p $(DATADIR) -1 -1

stubmap : % : $(DATADIR)/%.o5m
	$(call remove-file,$(DATADIR)/$*.mtiles)
	$(MAPCREATORDIR)/mapwrite.py -l $(LOGLEVEL) -k -f -p $(DATADIR) -2 -2

boundaries : $(DATADIR)/boundaries.o5m
	$(MAPCREATORDIR)/boundaries.py -l $(LOGLEVEL) -p $(DATADIR)

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

publish:
	rsync -vru --exclude='nativeindex' --exclude='lost+found' /gis/maps/* tanya.newf.ru:/gis/maps
	ssh tanya.newf.ru /gis/mapcreator/index.py


.PHONY: basemap stubmap boundaries maps world publish
