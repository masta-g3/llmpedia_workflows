// Master script to render dynamic dashboards based on LLM output

const {
    ResponsiveContainer, LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
    Tooltip, Legend, PieChart, Pie, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis,
    PolarRadiusAxis, Treemap, AreaChart, Area, ScatterChart, Scatter, ZAxis
} = Recharts;

// --- Component Implementations --- 
// These will receive props based on the `filled_parameters` from the LLM output

const TextComponent = ({ content }) => {
    // Basic implementation: render text content.
    // Consider adding markdown support later if needed.
    return React.createElement('p', null, content);
};

const BarChartComponent = ({ data = [], y_axis_label, x_axis_label, palette }) => {
    console.log("[BarChartComponent] Rendering with props:", { data, y_axis_label, x_axis_label, palette });
    if (!Array.isArray(data) || data.length === 0) {
        console.warn("[BarChartComponent] No valid data array provided.");
        return React.createElement('p', null, 'No data provided for Bar Chart.');
    }

    // Determine if we have a second value series
    const hasValue2 = data.some(item => item.value2 !== undefined && item.value2 !== null);
    const value1Key = 'value1'; // Fixed keys based on schema
    const value2Key = 'value2';
    // Safely access names, provide defaults
    const value1Name = data[0]?.value1_name || 'Value 1'; 
    const value2Name = hasValue2 ? (data[0]?.value2_name || 'Value 2') : null;

    const chartColors = palette?.colors || { chart_fill_1: '#8884d8', chart_fill_2: '#82ca9d', grid_stroke: '#ccc' };
    console.log("[BarChartComponent] Using colors:", chartColors, "Has Value 2:", hasValue2);

    try {
        return React.createElement(
            ResponsiveContainer,
            { width: "100%", height: 300 },
            React.createElement(
                BarChart,
                { data: data, margin: { top: 5, right: 30, left: 20, bottom: 45 } }, // Keep bottom margin for space
                React.createElement(CartesianGrid, { strokeDasharray: "3 3", stroke: chartColors.grid_stroke }),
                React.createElement(XAxis, { dataKey: "category", height: 50, label: x_axis_label ? { value: x_axis_label, position: 'insideBottom', offset: -15 } : null }), // Reduced height slightly, kept offset
                React.createElement(YAxis, { label: y_axis_label ? { value: y_axis_label, angle: -90, position: 'insideLeft' } : null }),
                React.createElement(Tooltip),
                React.createElement(Legend, { // Use wrapperStyle for positioning
                    wrapperStyle: {
                        position: 'relative',
                        marginTop: '10px', // Push legend down from chart area
                    }
                }),
                React.createElement(Bar, { dataKey: value1Key, name: value1Name, fill: chartColors.chart_fill_1 }),
                hasValue2 && React.createElement(Bar, { dataKey: value2Key, name: value2Name, fill: chartColors.chart_fill_2 })
            )
        );
    } catch (error) {
        console.error("[BarChartComponent] Error during Recharts element creation:", error);
        return React.createElement('p', { style: { color: 'red' } }, 'Error rendering Bar Chart.');
    }
};

const PieChartComponent = ({ data = [], palette }) => {
    console.log("[PieChartComponent] Rendering with props:", { data, palette });
    if (!Array.isArray(data) || data.length === 0) {
         console.warn("[PieChartComponent] No valid data array provided.");
        return React.createElement('p', null, 'No data provided for Pie Chart.');
    }

    const cellColors = palette?.recharts_cell_fills || ['#8884d8', '#82ca9d', '#ffc658', '#ff7f0e', '#1f77b4', '#aec7e8'];
    console.log("[PieChartComponent] Using cell colors:", cellColors);

    try {
        return React.createElement(
            ResponsiveContainer,
            { width: "100%", height: 300 },
            React.createElement(
                PieChart,
                null, // No specific props needed here
                React.createElement(
                    Pie,
                    {
                        data: data,
                        cx: "50%",
                        cy: "50%",
                        innerRadius: 60, // Make it a donut chart
                        outerRadius: 80,
                        fill: "#8884d8", // Default fill, overridden by Cells
                        paddingAngle: 5,
                        dataKey: "value", // Fixed key based on schema
                        nameKey: "name" // Use name for tooltips/legend
                    },
                    data.map((entry, index) => React.createElement(Cell, { key: `cell-${index}`, fill: cellColors[index % cellColors.length] }))
                ),
                React.createElement(Tooltip),
                React.createElement(Legend)
            )
        );
     } catch (error) {
        console.error("[PieChartComponent] Error during Recharts element creation:", error);
        return React.createElement('p', { style: { color: 'red' } }, 'Error rendering Pie Chart.');
    }
};

const LineChartComponent = ({ data = [], x_axis_label, y_axis_label, palette }) => {
    console.log("[LineChartComponent] Rendering with props:", { data, x_axis_label, y_axis_label, palette });
    if (!Array.isArray(data) || data.length === 0) {
        console.warn("[LineChartComponent] No valid data array provided.");
        return React.createElement('p', null, 'No data provided for Line Chart.');
    }

    const hasValue2 = data.some(item => item.y_value2 !== undefined && item.y_value2 !== null);
    const value1Key = 'y_value1';
    const value2Key = 'y_value2';
    const value1Name = data[0]?.y_value1_name || 'Value 1';
    const value2Name = hasValue2 ? (data[0]?.y_value2_name || 'Value 2') : null;
    const xValueKey = 'x_value';

    const chartColors = palette?.colors || { chart_fill_1: '#8884d8', chart_fill_2: '#82ca9d', grid_stroke: '#ccc' };
    console.log("[LineChartComponent] Using colors:", chartColors, "Has Value 2:", hasValue2);

    try {
        return React.createElement(
            ResponsiveContainer,
            { width: "100%", height: 300 },
            React.createElement(
                LineChart,
                { data: data, margin: { top: 5, right: 30, left: 20, bottom: 5 } }, 
                React.createElement(CartesianGrid, { strokeDasharray: "3 3", stroke: chartColors.grid_stroke }),
                React.createElement(XAxis, { dataKey: xValueKey, label: x_axis_label ? { value: x_axis_label, position: 'insideBottom', offset: -5 } : null }),
                React.createElement(YAxis, { label: y_axis_label ? { value: y_axis_label, angle: -90, position: 'insideLeft' } : null }),
                React.createElement(Tooltip),
                React.createElement(Legend),
                React.createElement(Line, { type: "monotone", dataKey: value1Key, name: value1Name, stroke: chartColors.chart_fill_1, strokeWidth: 2 }),
                hasValue2 && React.createElement(Line, { type: "monotone", dataKey: value2Key, name: value2Name, stroke: chartColors.chart_fill_2, strokeWidth: 2 })
            )
        );
    } catch (error) {
        console.error("[LineChartComponent] Error during Recharts element creation:", error);
        return React.createElement('p', { style: { color: 'red' } }, 'Error rendering Line Chart.');
    }
};

const RadarChartComponent = ({ data = [], radius_domain, palette }) => {
    console.log("[RadarChartComponent] Rendering with props:", { data, radius_domain, palette });
    if (!Array.isArray(data) || data.length === 0) {
         console.warn("[RadarChartComponent] No valid data array provided.");
        return React.createElement('p', null, 'No data provided for Radar Chart.');
    }

    const hasValue2 = data.some(item => item.value2 !== undefined && item.value2 !== null);
    const value1Key = 'value1';
    const value2Key = 'value2';
    const value1Name = data[0]?.value1_name || 'Value 1';
    const value2Name = hasValue2 ? (data[0]?.value2_name || 'Value 2') : null;
    const subjectKey = 'subject';

    const chartColors = palette?.colors || { chart_fill_1: '#8884d8', chart_fill_2: '#82ca9d' };
    
    // Determine radius axis domain
    let radiusAxisProps = {};
    if (Array.isArray(radius_domain) && radius_domain.length === 2) {
        radiusAxisProps.angle = 90;
        radiusAxisProps.domain = radius_domain;
    } else {
         // Infer from fullMark if available, otherwise default
        const fullMarkValue = data[0]?.fullMark;
        radiusAxisProps.angle = 90;
        radiusAxisProps.domain = [0, fullMarkValue || 'auto']; // Use 'auto' if no fullMark
    }
    console.log("[RadarChartComponent] Using colors:", chartColors, "Has Value 2:", hasValue2, "Radius Props:", radiusAxisProps);

    try {
        return React.createElement(
            ResponsiveContainer,
            { width: "100%", height: 300 },
            React.createElement(
                RadarChart,
                { outerRadius: "80%", data: data },
                React.createElement(PolarGrid, null),
                React.createElement(PolarAngleAxis, { dataKey: subjectKey }),
                React.createElement(PolarRadiusAxis, radiusAxisProps),
                React.createElement(Tooltip),
                React.createElement(Legend),
                React.createElement(Radar, { name: value1Name, dataKey: value1Key, stroke: chartColors.chart_fill_1, fill: chartColors.chart_fill_1, fillOpacity: 0.6 }),
                hasValue2 && React.createElement(Radar, { name: value2Name, dataKey: value2Key, stroke: chartColors.chart_fill_2, fill: chartColors.chart_fill_2, fillOpacity: 0.6 })
            )
        );
    } catch (error) {
        console.error("[RadarChartComponent] Error during Recharts element creation:", error);
        return React.createElement('p', { style: { color: 'red' } }, 'Error rendering Radar Chart.');
    }
};

// Custom content renderer for Treemap to apply palette colors
const TreemapContent = (props) => {
    const { root, depth, x, y, width, height, index, colors, name } = props;
    
    // Use modulo operator to cycle through colors based on depth or index
    const fillColor = colors[ (depth === 1 ? index : root.index + index) % colors.length]; 

    return (
        React.createElement('g',
            null,
            React.createElement('rect', {
                x: x,
                y: y,
                width: width,
                height: height,
                style: {
                    fill: fillColor,
                    stroke: '#fff',
                    strokeWidth: 2 / (depth + 1e-10),
                    strokeOpacity: 1 / (depth + 1e-10),
                },
            }),
            // Only render text if the box is large enough
            width > 50 && height > 25 ? 
            React.createElement('text', {
                x: x + width / 2,
                y: y + height / 2 + 7,
                textAnchor: "middle",
                fill: "#fff", // Consider adjusting based on fill color contrast
                fontSize: 14,
            }, name) : null 
        )
    );
};

const TreemapComponent = ({ data = [], palette }) => {
    console.log("[TreemapComponent] Rendering with props:", { data, palette });
    if (!Array.isArray(data) || data.length === 0) {
         console.warn("[TreemapComponent] No valid data array provided.");
        return React.createElement('p', null, 'No data provided for Treemap.');
    }

    const cellColors = palette?.recharts_cell_fills || ['#8884d8', '#82ca9d', '#ffc658', '#ff7f0e', '#1f77b4', '#aec7e8'];
     console.log("[TreemapComponent] Using cell colors:", cellColors);

    try {
        return React.createElement(
            ResponsiveContainer,
            { width: "100%", height: 300 },
            React.createElement(
                Treemap,
                {
                    data: data,
                    dataKey: "size", // Fixed key based on schema
                    ratio: 4 / 3,
                    stroke: "#fff",
                    fill: "#8884d8", // Default fill, overridden by content renderer
                    isAnimationActive: false, // Animation can be buggy with custom content
                    content: React.createElement(TreemapContent, { colors: cellColors })
                },
                React.createElement(Tooltip)
            )
        );
     } catch (error) {
        console.error("[TreemapComponent] Error during Recharts element creation:", error);
        return React.createElement('p', { style: { color: 'red' } }, 'Error rendering Treemap.');
    }
};

const AreaChartComponent = ({ data = [], x_axis_label, y_axis_label, stack_offset, palette }) => {
    console.log("[AreaChartComponent] Rendering with props:", { data, x_axis_label, y_axis_label, stack_offset, palette });
    if (!Array.isArray(data) || data.length === 0) {
        console.warn("[AreaChartComponent] No valid data array provided.");
        return React.createElement('p', null, 'No data provided for Area Chart.');
    }

    const hasValue2 = data.some(item => item.y_value2 !== undefined && item.y_value2 !== null);
    const value1Key = 'y_value1';
    const value2Key = 'y_value2';
    const value1Name = data[0]?.y_value1_name || 'Value 1';
    const value2Name = hasValue2 ? (data[0]?.y_value2_name || 'Value 2') : null;
    const xValueKey = 'x_value';
    const stackId = (stack_offset && stack_offset !== 'none') ? '1' : undefined; // Assign stackId if stacking

    const chartColors = palette?.colors || { chart_fill_1: '#8884d8', chart_fill_2: '#82ca9d', grid_stroke: '#ccc' };
    console.log("[AreaChartComponent] Using colors:", chartColors, "Has Value 2:", hasValue2, "Stack Offset:", stack_offset);
    
    try {
        return React.createElement(
            ResponsiveContainer,
            { width: "100%", height: 300 },
            React.createElement(
                AreaChart,
                { data: data, stackOffset: (stack_offset !== 'none' ? stack_offset : undefined), margin: { top: 5, right: 30, left: 20, bottom: 5 } }, 
                React.createElement(CartesianGrid, { strokeDasharray: "3 3", stroke: chartColors.grid_stroke }),
                React.createElement(XAxis, { dataKey: xValueKey, label: x_axis_label ? { value: x_axis_label, position: 'insideBottom', offset: -5 } : null }),
                React.createElement(YAxis, { label: y_axis_label ? { value: y_axis_label, angle: -90, position: 'insideLeft' } : null }),
                React.createElement(Tooltip),
                React.createElement(Legend),
                React.createElement(Area, { type: "monotone", dataKey: value1Key, name: value1Name, stackId: stackId, stroke: chartColors.chart_fill_1, fill: chartColors.chart_fill_1, fillOpacity: 0.6 }),
                hasValue2 && React.createElement(Area, { type: "monotone", dataKey: value2Key, name: value2Name, stackId: stackId, stroke: chartColors.chart_fill_2, fill: chartColors.chart_fill_2, fillOpacity: 0.6 })
            )
        );
    } catch (error) {
        console.error("[AreaChartComponent] Error during Recharts element creation:", error);
        return React.createElement('p', { style: { color: 'red' } }, 'Error rendering Area Chart.');
    }
};

const ScatterPlotComponent = ({ data = [], x_axis_label, y_axis_label, z_axis_label, series_name, palette }) => {
    console.log("[ScatterPlotComponent] Rendering with props:", { data, x_axis_label, y_axis_label, z_axis_label, series_name, palette });
    if (!Array.isArray(data) || data.length === 0) {
        console.warn("[ScatterPlotComponent] No valid data array provided.");
        return React.createElement('p', null, 'No data provided for Scatter Plot.');
    }

    const chartColors = palette?.recharts_cell_fills || ['#8884d8', '#82ca9d', '#ffc658', '#ff7f0e', '#1f77b4', '#aec7e8'];
    const gridColor = palette?.colors?.grid_stroke || '#ccc';
    const xKey = 'x';
    const yKey = 'y';
    const zKey = 'z'; // Optional, for tooltip/size
    const categoryKey = 'category'; // Optional, for grouping

    // Check if data is grouped by category
    const categories = [...new Set(data.filter(p => p.category).map(p => p.category))];
    const isGrouped = categories.length > 0;
    console.log("[ScatterPlotComponent] Using colors:", chartColors, "Is Grouped:", isGrouped, "Categories:", categories);
    
    // Prepare Scatter elements
    let scatterElements;
    if (isGrouped) {
        scatterElements = categories.map((cat, index) => {
            const categoryData = data.filter(p => p.category === cat);
            return React.createElement(Scatter, {
                key: cat,
                name: cat,
                data: categoryData,
                fill: chartColors[index % chartColors.length]
            });
        });
    } else {
        scatterElements = React.createElement(Scatter, {
            name: series_name || 'Data Points',
            data: data,
            fill: chartColors[0] // Use first color for single series
        });
    }
    
    try {
        return React.createElement(
            ResponsiveContainer,
            { width: "100%", height: 300 },
            React.createElement(
                ScatterChart,
                { margin: { top: 20, right: 20, bottom: 20, left: 20 } }, 
                React.createElement(CartesianGrid, { stroke: gridColor }),
                React.createElement(XAxis, { type: "number", dataKey: xKey, name: x_axis_label || 'X', label: x_axis_label ? { value: x_axis_label, position: 'insideBottom', offset: -5 } : null }),
                React.createElement(YAxis, { type: "number", dataKey: yKey, name: y_axis_label || 'Y', label: y_axis_label ? { value: y_axis_label, angle: -90, position: 'insideLeft' } : null }),
                React.createElement(ZAxis, { dataKey: zKey, name: z_axis_label || 'Z', range: [60, 400] }), // Optional: use Z for bubble size
                React.createElement(Tooltip, { cursor: { strokeDasharray: '3 3' } }),
                React.createElement(Legend),
                scatterElements // Add the Scatter component(s)
            )
        );
    } catch (error) {
        console.error("[ScatterPlotComponent] Error during Recharts element creation:", error);
        return React.createElement('p', { style: { color: 'red' } }, 'Error rendering Scatter Plot.');
    }
};

const ListComponent = ({ items = [], ordered = false }) => {
     console.log("[ListComponent] Rendering with props:", { items, ordered });
    if (!Array.isArray(items) || items.length === 0) {
        console.warn("[ListComponent] No valid items array provided.");
        return React.createElement('p', null, 'No items provided for list.');
    }

    const listType = ordered ? 'ol' : 'ul';
    const listStyle = ordered ? { listStyleType: 'decimal', marginLeft: '20px' } : { listStyleType: 'disc', marginLeft: '20px' };

    try {
        return React.createElement(
            listType,
            { style: listStyle },
            items.map((item, index) => React.createElement('li', { key: index }, item)) 
        );
    } catch (error) {
        console.error("[ListComponent] Error during element creation:", error);
        return React.createElement('p', { style: { color: 'red' } }, 'Error rendering list.');
    }
};

// --- Add placeholders and implementations for new components --- 

// Key-Value Component (HTML dl list)
const KeyValueComponent = ({ items = [], palette }) => {
    console.log("[KeyValueComponent] Rendering with props:", { items, palette });
    if (!Array.isArray(items) || items.length === 0) {
        console.warn("[KeyValueComponent] No valid items array provided.");
        return React.createElement('p', null, 'No key-value pairs provided.');
    }
    const textColor = palette?.colors?.text || '#000';
    const keyStyle = { fontWeight: 'bold', marginRight: '8px', color: textColor };
    const valueStyle = { color: textColor };
    const itemStyle = { marginBottom: '8px' };

    try {
        return React.createElement('div', { style: { color: textColor } },
            items.map((item, index) => 
                React.createElement('div', { key: index, style: itemStyle }, 
                    React.createElement('span', { style: keyStyle }, item.key ? item.key + ':' : '-'),
                    React.createElement('span', { style: valueStyle }, item.value || '-')
                )
            )
        );
    } catch (error) {
        console.error("[KeyValueComponent] Error during element creation:", error);
        return React.createElement('p', { style: { color: 'red' } }, 'Error rendering key-value list.');
    }
};

// Quote Block Component (HTML blockquote)
const QuoteComponent = ({ text, source, palette }) => {
    console.log("[QuoteComponent] Rendering with props:", { text, source, palette });
    if (!text) {
        console.warn("[QuoteComponent] No text provided.");
        return React.createElement('p', null, 'Quote text missing.');
    }
    const blockquoteStyle = {
        borderLeft: `4px solid ${palette?.colors?.primary || '#b31b1b'}`,
        paddingLeft: '15px',
        marginLeft: '0px',
        fontStyle: 'italic',
        color: palette?.colors?.text || '#333'
    };
    const sourceStyle = {
        display: 'block',
        marginTop: '10px',
        textAlign: 'right',
        fontSize: '0.9em',
        color: palette?.colors?.secondary || '#888'
    };

    try {
        return React.createElement('blockquote', { style: blockquoteStyle },
            React.createElement('p', { style: { margin: '0' } }, text),
            source && React.createElement('footer', { style: sourceStyle }, '\u2014 ', source) // Em dash
        );
    } catch (error) {
        console.error("[QuoteComponent] Error during element creation:", error);
        return React.createElement('p', { style: { color: 'red' } }, 'Error rendering quote.');
    }
};

// Comparison Table Component (HTML table)
const ComparisonTableComponent = ({ headers = [], rows = [], palette }) => {
    console.log("[ComparisonTableComponent] Rendering with props:", { headers, rows, palette });
    if (!Array.isArray(headers) || headers.length === 0 || !Array.isArray(rows) || rows.length === 0) {
        console.warn("[ComparisonTableComponent] Invalid headers or rows provided.");
        return React.createElement('p', null, 'Table data incomplete.');
    }
    const tableStyle = {
        width: '100%',
        borderCollapse: 'collapse',
        marginTop: '10px',
        color: palette?.colors?.text || '#000'
    };
    const thStyle = {
        border: `1px solid ${palette?.colors?.grid_stroke || '#ccc'}`,
        padding: '8px',
        textAlign: 'left',
        backgroundColor: palette?.colors?.primary || '#b31b1b',
        color: palette?.colors?.text_on_primary || '#fff'
    };
    const tdStyle = {
        border: `1px solid ${palette?.colors?.grid_stroke || '#ccc'}`,
        padding: '8px',
        textAlign: 'left'
    };

    try {
        return React.createElement('table', { style: tableStyle },
            React.createElement('thead', null,
                React.createElement('tr', null,
                    headers.map((header, index) => React.createElement('th', { key: index, style: thStyle }, header))
                )
            ),
            React.createElement('tbody', null,
                rows.map((row, rowIndex) =>
                    React.createElement('tr', { key: rowIndex },
                        row.map((cell, cellIndex) => React.createElement('td', { key: cellIndex, style: tdStyle }, cell))
                    )
                )
            )
        );
    } catch (error) {
        console.error("[ComparisonTableComponent] Error during element creation:", error);
        return React.createElement('p', { style: { color: 'red' } }, 'Error rendering table.');
    }
};

// Horizontal Bar Component (HTML/CSS progress bar style)
const HorizontalBarComponent = ({ items = [], palette }) => {
    console.log("[HorizontalBarComponent] Rendering with props:", { items, palette });
    if (!Array.isArray(items) || items.length === 0) {
        console.warn("[HorizontalBarComponent] No valid items array provided.");
        return React.createElement('p', null, 'No items provided for horizontal bars.');
    }
    const containerStyle = { width: '100%', color: palette?.colors?.text || '#000' };
    const itemStyle = { marginBottom: '15px' };
    const labelStyle = { display: 'block', marginBottom: '5px', fontSize: '0.9em' };
    const barContainerStyle = {
        width: '100%',
        backgroundColor: palette?.colors?.senary || '#eee',
        borderRadius: '4px',
        height: '20px',
        overflow: 'hidden',
        position: 'relative' // For text overlay
    };
    const barFillBaseStyle = {
        height: '100%',
        backgroundColor: palette?.colors?.primary || '#b31b1b',
        borderRadius: '4px 0 0 4px',
        transition: 'width 0.5s ease-in-out',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: palette?.colors?.text_on_primary || '#fff',
        fontSize: '0.8em',
        whiteSpace: 'nowrap',
        overflow: 'hidden'
    };

    try {
        return React.createElement('div', { style: containerStyle },
            items.map((item, index) => {
                const maxValue = item.max_value || 100;
                const percentage = Math.max(0, Math.min(100, (item.value / maxValue) * 100));
                const displayValue = item.display_value !== undefined ? item.display_value : item.value;
                const barFillStyle = { ...barFillBaseStyle, width: `${percentage}%` };

                return React.createElement('div', { key: index, style: itemStyle },
                    React.createElement('span', { style: labelStyle }, item.label),
                    React.createElement('div', { style: barContainerStyle },
                         React.createElement('div', { style: barFillStyle }, 
                            percentage > 10 ? displayValue : '' // Only show text if bar is wide enough
                         )
                    )
                );
            })
        );
    } catch (error) {
        console.error("[HorizontalBarComponent] Error during element creation:", error);
        return React.createElement('p', { style: { color: 'red' } }, 'Error rendering horizontal bars.');
    }
};

// Image Component (HTML img)
const ImageComponent = ({ image_url, alt_text, caption, palette }) => {
     console.log("[ImageComponent] Rendering with props:", { image_url, alt_text, caption, palette });
    if (!image_url) {
        console.warn("[ImageComponent] No image_url provided.");
        return React.createElement('p', null, 'Image URL missing.');
    }
    const containerStyle = { textAlign: 'center', marginTop: '10px' };
    const imgStyle = {
        maxWidth: '100%',
        maxHeight: '400px', // Limit height to prevent overly large images
        height: 'auto',
        border: `1px solid ${palette?.colors?.grid_stroke || '#ccc'}`,
        padding: '5px'
    };
    const captionStyle = {
        fontSize: '0.9em',
        fontStyle: 'italic',
        marginTop: '5px',
        color: palette?.colors?.text || '#555'
    };
    
    try {
        return React.createElement('div', { style: containerStyle },
            React.createElement('img', { src: image_url, alt: alt_text || 'Diagram from paper', style: imgStyle }),
            caption && React.createElement('p', { style: captionStyle }, caption)
        );
    } catch (error) {
        console.error("[ImageComponent] Error during element creation:", error);
        return React.createElement('p', { style: { color: 'red' } }, 'Error rendering image.');
    }
};

// --- Component Mapping --- 
const componentMap = {
    'text_v1': TextComponent,
    'bar_chart_v1': BarChartComponent,
    'pie_chart_v1': PieChartComponent,
    'line_chart_v1': LineChartComponent,
    'radar_chart_v1': RadarChartComponent,
    'treemap_v1': TreemapComponent,
    'area_chart_v1': AreaChartComponent,
    'scatter_plot_v1': ScatterPlotComponent,
    'list_v1': ListComponent,
    'key_value_v1': KeyValueComponent,
    'quote_v1': QuoteComponent,
    'comparison_table_v1': ComparisonTableComponent,
    'horizontal_bar_v1': HorizontalBarComponent,
    'image_v1': ImageComponent,
    // Add other components here as they are defined
};

// --- Dashboard Rendering Logic --- 

// FindingCard component (assumed to be globally available from html_template)
// const FindingCard = ({ title, description, chart, note }) => { ... };

// Main Dashboard Component
const DynamicDashboard = ({ dashboardStructure, palette }) => {
    if (!dashboardStructure || dashboardStructure.length === 0) {
        return React.createElement('p', null, 'Error: Dashboard structure data is missing.');
    }

    console.log("Rendering DynamicDashboard with structure:", dashboardStructure);
    console.log("Using palette:", palette);

    const defaultTab = dashboardStructure[0]?.tab_id || 'tab1';

    // Map dashboard structure to Tabs and FindingCards
    const tabTriggers = dashboardStructure.map(tabData => {
        return React.createElement(TabsTrigger, { key: tabData.tab_id, value: tabData.tab_id }, tabData.title || `Tab ${tabData.tab_id}`);
    });

    const tabContents = dashboardStructure.map(tabData => {
        const ComponentToRender = componentMap[tabData.chosen_component_id];
        let chartElement = null;

        if (ComponentToRender) {
            try {
                 // Pass palette colors if the component needs them (TODO: refine this)
                const componentProps = { ...tabData.filled_parameters, palette }; 
                chartElement = React.createElement(ComponentToRender, componentProps);
            } catch (error) {
                console.error(`Error rendering component ${tabData.chosen_component_id}:`, error);
                chartElement = React.createElement('p', { style: { color: 'red' } }, `Error rendering component: ${tabData.chosen_component_id}`);
            }
        } else {
            chartElement = React.createElement('p', { style: { color: 'orange' } }, `Component not found: ${tabData.chosen_component_id}`);
        }

        return React.createElement(
            TabsContent,
            { key: tabData.tab_id, value: tabData.tab_id },
            React.createElement(FindingCard, {
                title: tabData.title,
                description: tabData.description,
                chart: chartElement,
                note: tabData.note,
            })
        );
    });

    return React.createElement(
        'div',
        { className: "mx-auto", style: { backgroundColor: palette?.colors?.background || '#FFF' } }, // Use palette background
        React.createElement(
            Tabs,
            { defaultValue: defaultTab, className: "w-full" },
            ...tabTriggers,
            ...tabContents
        )
    );
};

// --- Initialization --- 

// Function to safely parse JSON from the DOM
const getJsonData = (elementId) => {
    const element = document.getElementById(elementId);
    if (!element) {
        console.error(`Element with ID '${elementId}' not found.`);
        return null;
    }
    try {
        return JSON.parse(element.textContent);
    } catch (error) {
        console.error(`Error parsing JSON from element '${elementId}':`, error);
        return null;
    }
};

// Render the dashboard
// Wrap initialization in a function to prevent auto-execution in test harness
function initializeDynamicDashboard() {
    const dashboardStructureData = getJsonData('dashboard-structure-data');
    const paletteData = getJsonData('palette-data'); // Expects the full palette object

    if (!dashboardStructureData) {
        console.warn("Dashboard structure data not found, aborting dynamic dashboard initialization.");
        // Optionally render an error message in the #root
        // ReactDOM.render(React.createElement('p', null, 'Error: Missing dashboard data.'), document.getElementById('root'));
        return; 
    }

    // Select the active palette (use default from paletteData if available, else fallback)
    const activePalette = paletteData?.palettes?.[paletteData?.default_palette || 'orange_toned'] || { 
        colors: { background: '#FFF8E1', chart_fill_1: '#FF8C00', chart_fill_2: '#FFA500', grid_stroke: '#ccc' }, // Enhanced fallback
        recharts_cell_fills: ['#FF8C00', '#FFA500', '#FFD700', '#E64A19']
    };

    ReactDOM.render(
        React.createElement(DynamicDashboard, { dashboardStructure: dashboardStructureData, palette: activePalette }),
        document.getElementById('root')
    );
}

// In a real dashboard scenario (not test harness), this function would be called.
// For now, we don't call it automatically. The Python backend will need to ensure
// the necessary data elements exist before potentially calling this via a small script tag.
// Example (to be added by Python later, if needed):
// if (document.getElementById('dashboard-structure-data')) {
//     initializeDynamicDashboard();
// } 
