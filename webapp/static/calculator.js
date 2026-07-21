$(function() {

    // === URL mod slugs ===

    var MOD_TO_SLUG = {
        'trait-double-grip': 'double-grip', 'trait-drunkard': 'drunkard',
        'trait-huge': 'huge', 'trait-tiny': 'tiny', 'trait-brute': 'brute',
        'perk-duelist': 'duelist', 'perk-killing-frenzy': 'killing-frenzy',
        'perk-head-hunter': 'head-hunter', 'perk-crippling-strikes': 'crippling-strikes',
        'perk-executioner': 'executioner', 'trait-juggler': 'juggler',
        'trait-killer-on-the-run': 'killer-on-the-run', 'injury-broken-arm': 'broken-arm',
        'injury-split-shoulder': 'split-shoulder', 'injury-cut-arm-sinew': 'cut-arm-sinew',
        'injury-injured-shoulder': 'injured-shoulder', 'status-dazed': 'dazed',
        'status-distracted': 'distracted', 'status-strange-mushrooms': 'strange-mushrooms'
    };

    // Slugs come from the database via data-slug attributes and skill.slug fields.
    // No on-the-fly slug generation.

    // === Weapon ===

    var currentSkills = [];
    var isEditMode = false;
    var statsEdited = false;

    function applyWeapon() {
        var opt = $('#weapon-select option:selected');
        $('#weapon-dropdown-selected').text(opt.text().trim());
        var min = opt.data('min');
        var max = opt.data('max');
        var ap = opt.data('ap');
        var dap = opt.data('dap');
        var hs = parseInt(opt.data('hs')) || 0;
        var hsVal = 0.25 + hs / 100;

        // Load skills, group by identical damage profiles
        var allSkills = opt.data('skills') || [];
        currentSkills = [];
        var seen = {};
        $.each(allSkills, function(i, s) {
            var key = s.name + '|' + s.piercing_perc + '|' + s.bonus_damage + '|' + s.headshot_bonus + '|' + (s.damage_mult || 1.0) + '|' + JSON.stringify(s.calc_params || {});
            if (!seen[key]) {
                seen[key] = true;
                currentSkills.push(s);
            }
        });

        // Build skill display
        var $radios = $('#skill-radios');
        $radios.empty();

        function buildSkillRadio(s, i) {
            var $label = $('<label>', {'class': 'checkbox'}).append(
                $('<input>', {type: 'radio', name: 'skill', value: i, checked: i === 0}),
                ' ' + s.name + ' ',
                $('<span>', {'class': 'hint'}).text(s.label || '')
            );
            if (s.damage_calculator_tooltip) $label.attr('title', s.damage_calculator_tooltip);
            return $label;
        }

        if (currentSkills.length > 1) {
            $.each(currentSkills, function(i, s) {
                $radios.append(buildSkillRadio(s, i));
            });
        } else if (currentSkills.length === 1) {
            $radios.append(buildSkillRadio(currentSkills[0], 0));
        }
        $radios.show();
        updateEnemyNote();

        // Stat card shows weapon base stats
        $('#ws-damage').text(min + ' – ' + max);
        $('#ws-ap').text(Math.round(parseFloat(ap) * 100) + '%');
        $('#ws-dap').text(Math.round(parseFloat(dap) * 100) + '%');
        $('#ws-hs').text('+' + hs + '%');

        // Edit mode inputs
        $('#damage_min').val(min);
        $('#damage_max').val(max);
        $('#piercing_perc').val(Math.round(parseFloat(ap) * 100));
        $('#damage_armor_perc').val(Math.round(parseFloat(dap) * 100));
        $('#headshot_chance').val(hs);

        setEditMode(false);
        statsEdited = false;
        $('#edit-toggle-row').show();
        $('#edit-toggle').html('&#9998; Edit Weapon Stats');
        $('#edit-reset').hide();
    }

    function setEditMode(on) {
        isEditMode = on;
        if (on) {
            $('.stat-value', '#weapon-stat-card').hide();
            $('.stat-edit', '#weapon-stat-card').show();
        } else {
            $('.stat-value', '#weapon-stat-card').show();
            $('.stat-edit', '#weapon-stat-card').hide();
        }
    }

    $('#weapon-select').on('change', applyWeapon);

    // Named weapon max stats: base * 1.30 for damage, base + 30 for armor%,
    // base + 16 for piercing%, base + 20 for headshot bonus.
    // Named weapons roll exactly 2 bonuses, but we allow any combination
    // in the editor since users may want theoretical max per stat.
    function setNamedMaxes() {
        var $sel = $('#weapon-select option:selected');
        var baseMin = parseInt($sel.data('min'));
        var baseMax = parseInt($sel.data('max'));
        var baseAp = Math.round(parseFloat($sel.data('ap')) * 100);
        var baseDap = Math.round(parseFloat($sel.data('dap')) * 100);
        var baseHs = parseInt($sel.data('hs')) || 0;
        $('#damage_min').attr('min', baseMin).attr('max', Math.round(baseMin * 1.30));
        $('#damage_max').attr('min', baseMax).attr('max', Math.round(baseMax * 1.30));
        $('#piercing_perc').attr('min', baseAp).attr('max', Math.min(100, baseAp + 16));
        $('#damage_armor_perc').attr('min', baseDap).attr('max', baseDap + 30);
        $('#headshot_chance').attr('min', baseHs).attr('max', baseHs + 20);
    }

    function clampEditInputs() {
        $('#weapon-stat-card input[type="number"]').each(function() {
            var val = parseInt($(this).val());
            var mn = parseInt($(this).attr('min'));
            var mx = parseInt($(this).attr('max'));
            if (!isNaN(mn) && val < mn) $(this).val(mn);
            if (!isNaN(mx) && val > mx) $(this).val(mx);
        });
    }

    $('#edit-toggle').on('click', function() {
        if (!isEditMode) {
            setNamedMaxes();
            setEditMode(true);
            $(this).html('&#128190; Save Weapon Stats');
            $('#edit-reset').show();
        } else {
            clampEditInputs();
            setEditMode(false);
            statsEdited = true;
            $(this).html('&#9998; Edit Weapon Stats');
            $('#ws-damage').text($('#damage_min').val() + ' \u2013 ' + $('#damage_max').val());
            $('#ws-ap').text($('#piercing_perc').val() + '%');
            $('#ws-dap').text($('#damage_armor_perc').val() + '%');
            $('#ws-hs').text('+' + $('#headshot_chance').val() + '%');
        }
    });

    $('#edit-reset').on('click', function() {
        setEditMode(false);
        $('#edit-toggle').html('&#9998; Edit Weapon Stats');
        applyWeapon();
    });

    // === Weapon dropdown ===

    function buildWeaponDropdown() {
        var $options = $('#weapon-options');
        $options.empty();

        $('#weapon-select option').each(function() {
            var $opt = $('<div>', {'class': 'weapon-option', 'data-value': $(this).val()});
            $opt.append($('<span>').text($(this).text().trim()));
            var tag = $(this).data('tag');
            if (tag) {
                $opt.append($('<span>', {'class': 'weapon-tag'}).text(tag));
            }
            $options.append($opt);
        });

        var selected = $('#weapon-select').val();
        $options.find('.weapon-option').each(function() {
            $(this).toggleClass('selected', $(this).data('value') === selected);
        });
    }

    $('#weapon-dropdown-selected').on('click', function(e) {
        e.stopPropagation();
        var $panel = $('#weapon-dropdown-panel');
        if ($panel.is(':visible')) {
            $panel.hide();
        } else {
            buildWeaponDropdown();
            var q = $('#weapon-search').val().toLowerCase();
            if (q) {
                $('#weapon-options .weapon-option').each(function() {
                    $(this).toggle($(this).text().toLowerCase().indexOf(q) !== -1);
                });
            }
            $panel.show();
            $('#weapon-search').focus();
        }
    });

    $('#weapon-search').on('input', function() {
        var q = $(this).val().toLowerCase();
        $('#weapon-options .weapon-option').each(function() {
            if ($(this).hasClass('weapon-option-custom')) {
                $(this).show();
                return;
            }
            var name = $(this).text().toLowerCase();
            $(this).toggle(name.indexOf(q) !== -1);
        });
        var hasVisible = $('#weapon-options .weapon-option:not(.weapon-option-custom):visible').length > 0;
        $('#weapon-options .weapon-divider').toggle(hasVisible);
    });

    $('#weapon-options').on('click', '.weapon-option', function() {
        var val = $(this).data('value');
        $('#weapon-select').val(val);
        $('#weapon-dropdown-selected').text($(this).text());
        $('#weapon-dropdown-panel').hide();
        applyWeapon();
    });

    $(document).on('click', function() {
        $('#weapon-dropdown-panel').hide();
        $('#enemy-dropdown-panel').hide();
    });

    $('#weapon-dropdown-panel, #enemy-dropdown-panel').on('click', function(e) {
        e.stopPropagation();
    });

    // === Enemy ===

    function formatRange(min, max) {
        if (min === max) return '' + min;
        return min + ' – ' + max;
    }

    function buildEnemyDropdown() {
        var $options = $('#enemy-options');
        $options.empty();
        var first = true;

        $('#enemy-select option').each(function() {
            var val = $(this).val();
            var cls = 'weapon-option' + (val === 'custom' ? ' weapon-option-custom' : '');
            $options.append($('<div>', {'class': cls, 'data-value': val})
                .text($(this).text().trim()));
            if (first && val === 'custom') {
                $options.append($('<div>', {'class': 'weapon-divider'}));
                first = false;
            }
        });

        var selected = $('#enemy-select').val();
        $options.find('.weapon-option').each(function() {
            $(this).toggleClass('selected', $(this).data('value') === selected);
        });
    }

    $('#enemy-dropdown-selected').on('click', function(e) {
        e.stopPropagation();
        var $panel = $('#enemy-dropdown-panel');
        if ($panel.is(':visible')) {
            $panel.hide();
        } else {
            buildEnemyDropdown();
            var q = $('#enemy-search').val().toLowerCase();
            if (q) {
                $('#enemy-options .weapon-option').each(function() {
                    $(this).toggle($(this).text().toLowerCase().indexOf(q) !== -1);
                });
            }
            $panel.show();
            $('#enemy-search').focus();
        }
    });

    $('#enemy-search').on('input', function() {
        var q = $(this).val().toLowerCase();
        $('#enemy-options .weapon-option').each(function() {
            $(this).toggle($(this).text().toLowerCase().indexOf(q) !== -1);
        });
    });

    $('#enemy-options').on('click', '.weapon-option', function() {
        var val = $(this).data('value');
        $('#enemy-select').val(val);
        $('#enemy-dropdown-selected').text($(this).text());
        $('#enemy-dropdown-panel').hide();
        applyEnemy();
    });

    function isCustomBrother() {
        return $('#enemy-select').val() === 'custom';
    }

    function applyEnemy() {
        var opt = $('#enemy-select option:selected');
        $('#enemy-dropdown-selected').text(opt.text().trim());

        if (isCustomBrother()) {
            $('#enemy-stats').hide();
            $('#enemy-note').hide();
            $('#custom-brother-panel').show();
            return;
        }

        $('#enemy-stats').show();
        $('#enemy-note').show();
        $('#custom-brother-panel').hide();

        var hp = opt.data('hp');
        var bodyMin = opt.data('body-min');
        var bodyMax = opt.data('body-max');
        var headMin = opt.data('head-min');
        var headMax = opt.data('head-max');
        var perks = opt.data('perks') || [];

        $('#es-hp').text(hp);
        $('#es-body').text(formatRange(bodyMin, bodyMax));
        $('#es-head').text(formatRange(headMin, headMax));

        if (perks.length > 0) {
            $('#es-perks').html(perks.join('<br>'));
        } else {
            $('#es-perks').text('none');
        }

        // Racial trait
        var racialTrait = opt.data('racial-trait') || '';
        var racialRes = opt.data('racial-resistances') || [];
        var racialImm = opt.data('racial-immunities') || [];
        var hasRacial = racialTrait || racialRes.length > 0 || racialImm.length > 0;

        if (hasRacial) {
            var label = racialTrait || 'Racial Abilities';
            var parts = [];
            if (racialImm.length > 0) parts.push(racialImm.join(', '));
            if (racialRes.length > 0) parts.push('Damage Resistances');
            var summary = parts.length > 0 ? ' (' + parts.join(', ') + ')' : '';
            $('#es-racial').html('<span class="racial-link" id="racial-info-link"><span class="racial-link-text">' + label + '</span> \u24d8</span>');

            // Store data for modal
            $('#es-racial').data('trait', racialTrait);
            $('#es-racial').data('resistances', racialRes);
            $('#es-racial').data('immunities', racialImm);
            $('#es-racial').data('armor-dmg-perc', parseFloat(opt.data('armor-dmg-perc')) || 1.0);
            $('#es-racial').data('heal-per-turn', parseInt(opt.data('heal-per-turn')) || 0);
            $('#es-racial').data('enemy-name', opt.text().trim());
        } else {
            $('#es-racial').text('none');
        }
    }

    $('#enemy-select').on('change', applyEnemy);

    // Custom brother: nimble mult from armor fatigue - bb-damage-engine's ONE
    // JavaScript home (bbEngineAttack.nimbleMultiplier, loaded from the bb-damage-engine
    // repo at /bb-damage-engine/attack.js). No copied formula here.
    function updateNimblePct() {
        var fat = parseInt($('#cb-armor-fatigue').val()) || 0;
        var mult = window.bbEngineAttack.nimbleMultiplier(fat);
        $('#cb-nimble-pct').text('HP dmg x' + (mult * 100).toFixed(1) + '%');
    }

    $('#cb-nimble').on('change', updateNimblePct);

    $('#cb-armor-fatigue').on('input', updateNimblePct);

    // Custom brother: Battle Forged percentage from armor values
    // BB formula: forge_mult = max(0.0, 1.0 - totalArmor * 0.0005)
    function updateBfPct() {
        var body = parseInt($('#cb-body').val()) || 0;
        var head = parseInt($('#cb-head').val()) || 0;
        var mult = Math.max(0.0, 1.0 - (body + head) * 0.0005);
        $('#cb-bf-pct').text('armor dmg x' + (mult * 100).toFixed(1) + '%');
    }

    $('#cb-battle-forged').on('change', updateBfPct);

    $('#cb-body, #cb-head').on('input', function() {
        if ($('#cb-battle-forged').is(':checked')) updateBfPct();
    });

    // Custom brother: defensive perks modal
    $('#cb-perks-toggle').on('click', function() {
        $('#cb-perks-modal').show();
    });

    $('#cb-perks-modal-close').on('click', function() {
        $('#cb-perks-modal').hide();
        updateCbPerksSummary();
    });

    $('#cb-perks-modal').on('click', function(e) {
        if (e.target === this) {
            $(this).hide();
            updateCbPerksSummary();
        }
    });

    function updateCbPerksSummary() {
        var items = [];
        $('#cb-perks-modal input:checked').each(function() {
            var label = $(this).parent().clone().children('span,input').remove().end().text().trim();
            items.push(label);
        });
        $('#cb-perks-summary').text(items.length > 0 ? items.join(', ') : '- none -');
    }

    // Racial trait modal
    $(document).on('click', '#racial-info-link', function() {
        var $el = $('#es-racial');
        var trait = $el.data('trait') || '';
        var res = $el.data('resistances') || [];
        var imm = $el.data('immunities') || [];
        var armorDmgPerc = $el.data('armor-dmg-perc') || 1.0;
        var healPerTurn = $el.data('heal-per-turn') || 0;
        var enemyName = $el.data('enemy-name') || 'Enemy';

        $('#racial-modal-title').text(enemyName + (trait ? ' \u2014 ' + trait : ''));

        var html = '';
        // Special modifiers
        if (armorDmgPerc !== 1.0 || healPerTurn > 0) {
            html += '<div class="racial-section"><h4>Special</h4><ul>';
            if (armorDmgPerc !== 1.0) {
                var reduction = Math.round((1.0 - armorDmgPerc) * 100);
                html += '<li>Armor takes ' + reduction + '% less damage</li>';
            }
            if (healPerTurn > 0) {
                var hp = parseInt($('#es-hp').text()) || 0;
                var healHp = Math.floor(hp * healPerTurn / 100);
                html += '<li>Heals ' + healHp + ' HP per turn (' + healPerTurn + '% of ' + hp + ')</li>';
            }
            html += '</ul></div>';
        }
        if (imm.length > 0) {
            html += '<div class="racial-section"><h4>Immunities</h4><ul>';
            $.each(imm, function(i, s) { html += '<li>' + s + '</li>'; });
            html += '</ul></div>';
        }
        if (res.length > 0) {
            html += '<div class="racial-section"><h4>Damage Resistances</h4>';
            html += '<table class="racial-table"><tr><th>Skill</th><th>Damage</th></tr>';
            $.each(res, function(i, r) {
                html += '<tr><td>' + r.skill + '</td><td>' + r.percent + '%</td></tr>';
            });
            html += '</table></div>';
        }
        if (!html) html = '<p>No special racial abilities.</p>';

        $('#racial-modal-body').html(html);
        $('#racial-modal').show();
    });

    $('#racial-modal-close, #racial-modal').on('click', function(e) {
        if (e.target === this) $('#racial-modal').hide();
    });

    function updateEnemyNote() {
        var skill = getSelectedSkill();
        var label = skill ? (skill.label || '') : '';
        var name = skill ? (skill.name || '') : '';
        var isBleedSkill = label.toLowerCase().indexOf('bleed') !== -1 || name.toLowerCase().indexOf('cleave') !== -1 || name.toLowerCase().indexOf('whip') !== -1 || name.toLowerCase().indexOf('rupture') !== -1;
        var imm = $('#es-racial').data('immunities') || [];
        var bleedImmune = false;
        $.each(imm, function(i, s) { if (s.indexOf('Bleeding') !== -1) bleedImmune = true; });
        if (isBleedSkill && bleedImmune) {
            $('#enemy-note').text('This enemy is immune to bleeding.');
        } else {
            $('#enemy-note').text('');
        }
    }

    $(document).on('change', 'input[name="skill"]', updateEnemyNote);

    // === Calculate ===

    function getSelectedSkill() {
        if (currentSkills.length === 0) return null;
        if (currentSkills.length === 1) return currentSkills[0];
        var idx = parseInt($('input[name="skill"]:checked').val()) || 0;
        return currentSkills[idx];
    }

    function doCalculate() {
        var wSlug = $('#weapon-select option:selected').data('slug');
        var eSlug = $('#enemy-select option:selected').data('slug');
        var parts = ['weapon=' + wSlug, 'enemy=' + eSlug];

        var skill = getSelectedSkill();
        if (skill) parts.push('skill=' + skill.slug);

        var mods = [];
        var modCheckboxes = '#trait-double-grip, #trait-drunkard, #trait-huge, #trait-tiny, #trait-brute, #perk-duelist, #perk-killing-frenzy, #perk-head-hunter, #perk-crippling-strikes, #perk-executioner, #trait-juggler, #trait-killer-on-the-run, #injury-broken-arm, #injury-split-shoulder, #injury-cut-arm-sinew, #injury-injured-shoulder, #status-dazed, #status-distracted, #status-strange-mushrooms';
        $(modCheckboxes).each(function() {
            if ($(this).is(':checked')) mods.push(MOD_TO_SLUG[this.id] || this.id);
        });
        if (mods.length) parts.push('mods=' + mods.join('_'));

        // Attacker buff
        var buffSlug = $('#attacker-buff option:selected').data('slug');
        if (buffSlug) {
            parts.push('buff=' + buffSlug);
        }

        // Champion
        if ($('#buff-champion').is(':checked')) {
            parts.push('champion=1');
        }

        // Custom brother defender stats
        if (isCustomBrother()) {
            parts.push('cb_hp=' + $('#cb-hp').val());
            parts.push('cb_body=' + $('#cb-body').val());
            parts.push('cb_head=' + $('#cb-head').val());
            var cbPerks = [];
            if ($('#cb-battle-forged').is(':checked')) cbPerks.push('bf');
            if ($('#cb-nimble').is(':checked')) cbPerks.push('nimble');
            if ($('#cb-steel-brow').is(':checked')) cbPerks.push('sb');
            if ($('#cb-nine-lives').is(':checked')) cbPerks.push('nl');
            if ($('#cb-resilient').is(':checked')) cbPerks.push('res');
            if ($('#cb-indomitable').is(':checked')) cbPerks.push('indom');
            if (cbPerks.length) parts.push('cb_perks=' + cbPerks.join('_'));
            if ($('#cb-nimble').is(':checked')) {
                parts.push('cb_fat=' + $('#cb-armor-fatigue').val());
            }
        }

        // Always send weapon stats from inputs — catches unsaved edits
        var $sel = $('#weapon-select option:selected');
        var defMin = $sel.data('min'), defMax = $sel.data('max');
        var defAp = Math.round(parseFloat($sel.data('ap')) * 100);
        var defDap = Math.round(parseFloat($sel.data('dap')) * 100);
        var defHs = parseInt($sel.data('hs')) || 0;
        var curMin = $('#damage_min').val(), curMax = $('#damage_max').val();
        var curAp = $('#piercing_perc').val(), curDap = $('#damage_armor_perc').val();
        var curHs = $('#headshot_chance').val();
        if (curMin != defMin || curMax != defMax || curAp != defAp
                || curDap != defDap || curHs != defHs) {
            parts.push('dmin=' + curMin);
            parts.push('dmax=' + curMax);
            parts.push('ap=' + curAp);
            parts.push('dap=' + curDap);
            parts.push('hs=' + curHs);
        }

        var url = '/?' + parts.join('&') + window.location.hash;
        if (window.location.href === url || window.location.href === window.location.origin + url) {
            window.location.reload();
        } else {
            window.location = url;
        }
    }

    $('#calculate-btn').on('click', function() {
        var isTwoHanded = String($('#weapon-select option:selected').data('two-handed')) === 'true';
        var warnings = [];
        if (isTwoHanded && $('#trait-double-grip').is(':checked'))
            warnings.push('Double Grip only works with 1-handed weapons.');
        if (isTwoHanded && $('#perk-duelist').is(':checked'))
            warnings.push('Duelist only works with 1-handed weapons.');
        var skillName = $('#skill-select option:selected').text().trim();
        if (skillName === 'Puncture' && $('#trait-double-grip').is(':checked'))
            warnings.push('Double Grip does not apply to Puncture.');
        if (skillName === 'Puncture') {
            var hsConflicts = [];
            if ($('#perk-head-hunter').is(':checked')) hsConflicts.push('Head Hunter');
            if ($('#trait-brute').is(':checked')) hsConflicts.push('Brute');
            if ($('#trait-juggler').is(':checked')) hsConflicts.push('Juggler');
            if ($('#trait-killer-on-the-run').is(':checked')) hsConflicts.push('Killer on the Run');
            if (hsConflicts.length > 0)
                warnings.push(hsConflicts.join(', ') + ' has no effect: Puncture never headshots.');
        }
        if (warnings.length > 0) {
            $('#warning-modal-body').html('<p>' + warnings.join('</p><p>') + '</p><p>These modifiers will be ignored.</p>');
            $('#warning-modal').show();
            return;
        }
        doCalculate();
    });

    $('#warning-modal-ok').on('click', function() {
        $('#warning-modal').hide();
        doCalculate();
    });
    $('#warning-modal-cancel, #warning-modal-x').on('click', function() {
        $('#warning-modal').hide();
    });
    $('#warning-modal').on('click', function(e) {
        if (e.target === this) $(this).hide();
    });

    // === Histogram ===

    function drawHistogram(distribution, title, emptyReason) {
        var canvas = document.getElementById('histogram');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');

        var dpr = window.devicePixelRatio || 1;
        var container = canvas.parentElement;
        var isMobile = window.innerWidth < 768;
        var barCount = (distribution && distribution.length) || 1;
        var minBarW = 50;

        // Reset canvas so container measures its natural width
        canvas.style.width = '0';
        var containerW = container.clientWidth;

        var w;
        if (isMobile) {
            w = Math.max(containerW, barCount * minBarW + 70);
            container.style.overflowX = 'auto';
        } else if (barCount >= 10) {
            w = Math.max(containerW, barCount * minBarW + 70);
            container.style.overflowX = 'auto';
        } else {
            w = containerW;
            container.style.overflowX = 'hidden';
        }

        canvas.width = w * dpr;
        canvas.height = 300 * dpr;
        canvas.style.width = w + 'px';
        canvas.style.height = '300px';
        ctx.scale(dpr, dpr);
        var h = 300;
        var pad = {top: 15, right: 20, bottom: 50, left: 50};
        var chartW = w - pad.left - pad.right;
        var chartH = h - pad.top - pad.bottom;

        ctx.clearRect(0, 0, w, h);
        if (!distribution || distribution.length === 0) {
            ctx.fillStyle = '#999';
            ctx.font = '13px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(emptyReason || 'No data', w / 2, h / 2);
            return;
        }

        var maxPct = Math.max.apply(null, distribution.map(function(d) { return d.percent; }));
        var barCount = distribution.length;
        var barWidth = Math.min(40, chartW / barCount - 4);
        var gap = (chartW - barWidth * barCount) / (barCount + 1);

        var yMax = 100;

        ctx.strokeStyle = '#ddd';
        ctx.lineWidth = 1;
        ctx.font = '13px sans-serif';
        ctx.fillStyle = '#666';
        ctx.textAlign = 'right';
        for (var i = 0; i <= 5; i++) {
            var val = (yMax / 5) * i;
            var y = pad.top + chartH - (val / yMax) * chartH;
            ctx.beginPath();
            ctx.moveTo(pad.left, y);
            ctx.lineTo(w - pad.right, y);
            ctx.stroke();
            ctx.fillText(Math.round(val) + '%', pad.left - 5, y + 4);
        }

        distribution.forEach(function(d, i) {
            var x = pad.left + gap + i * (barWidth + gap);
            var barH = (d.percent / yMax) * chartH;
            var y = pad.top + chartH - barH;

            ctx.fillStyle = '#c0392b';
            ctx.fillRect(x, y, barWidth, barH);

            ctx.fillStyle = '#333';
            ctx.textAlign = 'center';
            ctx.font = '13px sans-serif';
            var hitLabel = d.hits + (d.hits === 1 ? ' Hit' : ' Hits');
            ctx.fillText(hitLabel, x + barWidth / 2, h - pad.bottom + 18);

            if (d.percent >= 1) {
                ctx.font = '13px sans-serif';
                if (y - 5 < pad.top + 10) {
                    ctx.fillStyle = '#fff';
                    ctx.fillText(d.percent.toFixed(1) + '%', x + barWidth / 2, y + 15);
                } else {
                    ctx.fillStyle = '#333';
                    ctx.fillText(d.percent.toFixed(1) + '%', x + barWidth / 2, y - 5);
                }
            }
        });

        ctx.fillStyle = '#333';
        ctx.font = 'bold 13px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('# Hits: ' + (title || 'Distribution'), w / 2, h - 2);
    }

    // === Extra modal ===

    // === Background dropdown ===

    $('#bg-dropdown-selected').on('click', function() {
        $('#bg-dropdown-panel').toggle();
    });

    $(document).on('click', function(e) {
        if (!$(e.target).closest('#bg-dropdown').length) {
            $('#bg-dropdown-panel').hide();
        }
    });

    $('.bg-option').on('click', function() {
        var val = $(this).data('value');
        var name = $(this).find('span:first').text().trim();
        $('#background-select').val(val);
        $('#bg-dropdown-selected').text(name || 'None');
        $('.bg-option').removeClass('selected');
        $(this).addClass('selected');
        $('#bg-dropdown-panel').hide();
        $('#trait-juggler').prop('checked', val === 'juggler');
        $('#trait-killer-on-the-run').prop('checked', val === 'killer-on-the-run');
    });

    // === Buff dropdown ===

    var selectedBuff = '';

    $('#buff-dropdown-selected').on('click', function() {
        $('#buff-dropdown-panel').toggle();
    });

    $(document).on('click', function(e) {
        if (!$(e.target).closest('#buff-dropdown').length) {
            $('#buff-dropdown-panel').hide();
        }
    });

    $('#buff-dropdown-panel .buff-option').on('click', function() {
        var val = $(this).data('value');
        var name = $(this).find('span:first').text().trim();
        selectedBuff = val;
        $('#attacker-buff').val(val);
        $('#buff-dropdown-selected').text(name || 'None');
        $('#buff-dropdown-panel .buff-option').removeClass('selected');
        $(this).addClass('selected');
        $('#buff-dropdown-panel').hide();
    });

    function updateExtraSummary() {
        var items = [];
        // 1. Background
        var bgText = $('#background-select option:selected').text().trim();
        if (bgText && bgText !== 'None') items.push(bgText.split(' (')[0]);
        // 2. Injuries, status effects
        $('#extra-modal input:checked').not('#buff-champion').not('#trait-juggler').not('#trait-killer-on-the-run').each(function() {
            var label = $(this).parent().clone().children('span,input').remove().end().text().trim();
            items.push(label);
        });
        // 3. Attacker buff
        var buffName = $('#buff-dropdown-selected').text().trim();
        if (buffName && buffName !== 'None') items.push(buffName);
        // 4. Champion
        if ($('#buff-champion').is(':checked')) items.push('Champion');
        $('#extra-summary').text(items.length > 0 ? items.join(', ') : '- none -');
    }

    $('#extra-toggle').on('click', function() {
        $('#extra-modal').show();
    });

    $('#extra-modal-close').on('click', function() {
        $('#extra-modal').hide();
        updateExtraSummary();
    });

    $('#extra-modal').on('click', function(e) {
        if (e.target === this) {
            $(this).hide();
            updateExtraSummary();
        }
    });

    // === Init ===

    applyWeapon();
    applyEnemy();

    // Restore edited weapon stats from URL
    var params = new URLSearchParams(window.location.search);
    if (params.get('dmin')) {
        $('#damage_min').val(params.get('dmin'));
        $('#damage_max').val(params.get('dmax'));
        $('#piercing_perc').val(params.get('ap'));
        $('#damage_armor_perc').val(params.get('dap'));
        $('#headshot_chance').val(params.get('hs'));
        $('#ws-damage').text(params.get('dmin') + ' \u2013 ' + params.get('dmax'));
        $('#ws-ap').text(params.get('ap') + '%');
        $('#ws-dap').text(params.get('dap') + '%');
        $('#ws-hs').text('+' + params.get('hs') + '%');
        statsEdited = true;
        $('#edit-reset').show();
    }

    // Restore background from URL (checkboxes are hidden, sync dropdown)
    if ($('#trait-juggler').is(':checked')) {
        $('.bg-option[data-value="juggler"]').click();
    } else if ($('#trait-killer-on-the-run').is(':checked')) {
        $('.bg-option[data-value="killer-on-the-run"]').click();
    }

    // Restore champion from URL
    if (params.get('champion') === '1') {
        $('#buff-champion').prop('checked', true);
    }

    // Restore attacker buff from URL
    if (params.get('buff')) {
        var bSlug = params.get('buff');
        $('#buff-dropdown-panel .buff-option').each(function() {
            if (String($(this).data('slug')) === bSlug) {
                $(this).click();
                return false;
            }
        });
    }

    // Restore custom brother from URL
    if (params.get('cb_hp')) {
        $('#cb-hp').val(params.get('cb_hp'));
        $('#cb-body').val(params.get('cb_body'));
        $('#cb-head').val(params.get('cb_head'));
        var cbPerks = (params.get('cb_perks') || '').split('_');
        if (cbPerks.indexOf('bf') !== -1) {
            $('#cb-battle-forged').prop('checked', true);
            updateBfPct();
        }
        if (cbPerks.indexOf('nimble') !== -1) {
            $('#cb-nimble').prop('checked', true);
            $('#cb-armor-fatigue').val(params.get('cb_fat') || 15);
            updateNimblePct();
        }
        if (cbPerks.indexOf('sb') !== -1) $('#cb-steel-brow').prop('checked', true);
        if (cbPerks.indexOf('nl') !== -1) $('#cb-nine-lives').prop('checked', true);
        if (cbPerks.indexOf('res') !== -1) $('#cb-resilient').prop('checked', true);
        if (cbPerks.indexOf('indom') !== -1) $('#cb-indomitable').prop('checked', true);
        updateCbPerksSummary();
    }

    // Restore skill selection from URL
    if (params.get('skill')) {
        var sSlug = params.get('skill');
        $('input[name="skill"]').each(function() {
            var idx = parseInt($(this).val());
            if (currentSkills[idx] && currentSkills[idx].slug === sSlug) {
                $(this).prop('checked', true);
                return false;
            }
        });
        updateEnemyNote();
    }

    // Update extra summary if mods are pre-checked
    updateExtraSummary();

    // Draw histogram from server-rendered data
    var HISTOGRAM_TITLES = {
        kill: 'Hits to Kill Distribution',
        injury: 'Hits to Injure Distribution',
        resolve: 'Morale Check Distribution',
        fearsome: 'Morale Check Distribution with Fearsome'
    };

    var dataEl = document.getElementById('histogram-data');
    var histogramData = dataEl ? JSON.parse(dataEl.textContent) : null;
    if (histogramData) {
        var injuryImmune = histogramData.injury_immune;
        var moraleImmune = histogramData.morale_immune;

        function emptyReason(tab) {
            if (tab === 'injury') {
                return injuryImmune
                    ? 'Enemy is immune to injuries'
                    : 'Weapon does not deal enough damage to injure this enemy';
            }
            if (tab === 'resolve' || tab === 'fearsome') {
                return moraleImmune
                    ? 'Enemy is immune to morale'
                    : 'Weapon does not deal enough damage to trigger morale check';
            }
            return 'No data';
        }

        var activeTab = (window.location.hash.replace('#', '') || 'kill');
        if (!HISTOGRAM_TITLES[activeTab]) activeTab = 'kill';
        $('.histogram-tab').removeClass('active');
        $('.histogram-tab[data-tab="' + activeTab + '"]').addClass('active');
        drawHistogram(histogramData[activeTab], HISTOGRAM_TITLES[activeTab], emptyReason(activeTab));

        $('.histogram-tab').on('click', function(e) {
            e.preventDefault();
            $('.histogram-tab').removeClass('active');
            $(this).addClass('active');
            var tab = $(this).data('tab');
            var hash = tab === 'kill' ? '' : '#' + tab;
            history.replaceState(null, '', window.location.pathname + window.location.search + hash);
            drawHistogram(histogramData[tab], HISTOGRAM_TITLES[tab], emptyReason(tab));
        });
    }

});
