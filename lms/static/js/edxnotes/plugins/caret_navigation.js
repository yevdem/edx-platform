;(function (define, undefined) {
'use strict';
define(['jquery', 'underscore', 'annotator'], function ($, _, Annotator) {
    /**
     * The CaretNavigation Plugin which allows notes creation when users use
     * caret navigation to select the text.
     * Use `Ctrl + SPACE` or `Ctrl + ENTER` to open the editor.
     **/
    Annotator.Plugin.CaretNavigation = function () {
        // Call the Annotator.Plugin constructor this sets up the element and
        // options properties.
        _.bindAll(this, 'onKeyUp');
        Annotator.Plugin.apply(this, arguments);
    };

    $.extend(Annotator.Plugin.CaretNavigation.prototype, new Annotator.Plugin(), {
        pluginInit: function () {
            $(document).on('keyup', this.onKeyUp);
        },

        destroy: function () {
            $(document).off('keyup', this.onKeyUp);
        },

        isShortcut: function (event) {
            var shortcuts = [$.ui.keyCode.SPACE, $.ui.keyCode.ENTER];
            return event.ctrlKey && _.contains(shortcuts, event.which);
        },

        hasSelection: function (ranges) {
            return (ranges || []).length;
        },

        onKeyUp: function (event) {
            var annotator = this.annotator,
                isAnnotator, annotation, highlights, position, save, cancel, cleanup;

            // Do nothing if not a shortcut.
            if (!this.isShortcut(event)) {
                return true;
            }
            // Get the currently selected ranges.
            annotator.selectedRanges = annotator.getSelectedRanges();
            // Do nothing if there is no selection
            if (!this.hasSelection(annotator.selectedRanges)) {
                return true;
            }

            isAnnotator = _.some(annotator.selectedRanges, function (range) {
                return annotator.isAnnotator(range.commonAncestor);
            });

            // Do nothing if we are in Annotator.
            if (isAnnotator) {
                return true;
            }
            // Show a temporary highlight so the user can see what they selected
            // Also extract the quotation and serialize the ranges
            annotation = annotator.setupAnnotation(annotator.createAnnotation());
            highlights = $(annotation.highlights).addClass('annotator-hl-temporary');

            if (annotator.adder.is(':visible')) {
                position = annotator.adder.position();
                annotator.adder.hide();
            } else {
                position = highlights.last().position();
            }

            // Subscribe to the editor events
            // Make the highlights permanent if the annotation is saved
            save = function () {
                cleanup();
                highlights.removeClass('annotator-hl-temporary');
                // Fire annotationCreated events so that plugins can react to them
                annotator.publish('annotationCreated', [annotation]);
            };

            // Remove the highlights if the edit is cancelled
            cancel = function () {
                cleanup();
                annotator.deleteAnnotation(annotation);
            };

            // Don't leak handlers at the end
            cleanup = function () {
                annotator.unsubscribe('annotationEditorHidden', cancel);
                annotator.unsubscribe('annotationEditorSubmit', save);
            };

            annotator.subscribe('annotationEditorHidden', cancel);
            annotator.subscribe('annotationEditorSubmit', save);

            // Display the editor.
            annotator.showEditor(annotation, position);
            event.preventDefault();
        }
    });
});
}).call(this, define || RequireJS.define);
