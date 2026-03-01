<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" styleCategories="Symbology|Labeling" simplifyDrawingHints="1" simplifyDrawingTol="1" simplifyAlgorithm="0" simplifyLocal="1" simplifyMaxScale="1">
  <renderer-v2 type="categorizedSymbol" attr="LU_GENERAL" symbollevels="0" enableorderby="0">
    <categories>
      <category symbol="0" value="Residential" label="Residential (430,570)" render="true"/>
      <category symbol="1" value="Vacant" label="Vacant (19,254)" render="true"/>
      <category symbol="2" value="Retail / Commercial" label="Retail / Commercial (6,818)" render="true"/>
      <category symbol="3" value="Industrial" label="Industrial (4,617)" render="true"/>
      <category symbol="4" value="Agricultural" label="Agricultural (2,762)" render="true"/>
      <category symbol="5" value="Office" label="Office (3,664)" render="true"/>
      <category symbol="6" value="Miscellaneous" label="Miscellaneous (12,138)" render="true"/>
      <category symbol="7" value="Public / Utilities" label="Public / Utilities (1,684)" render="true"/>
      <category symbol="8" value="Church / Welfare" label="Church / Welfare (1,244)" render="true"/>
      <category symbol="9" value="Care / Health" label="Care / Health" render="true"/>
      <category symbol="10" value="Recreational" label="Recreational" render="true"/>
      <category symbol="11" value="" label="Unknown / NULL" render="true"/>
    </categories>
    <symbols>
      <!-- Residential - muted since it dominates (87.6%) -->
      <symbol name="0" type="fill" alpha="0.6" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="251,233,199,255"/>
          <prop k="outline_color" v="200,185,155,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.1"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <!-- Vacant - bright red -->
      <symbol name="1" type="fill" alpha="0.9" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="230,57,70,255"/>
          <prop k="outline_color" v="150,30,40,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.4"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <!-- Retail / Commercial - steel blue -->
      <symbol name="2" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="69,123,157,255"/>
          <prop k="outline_color" v="45,80,105,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <!-- Industrial - purple-gray -->
      <symbol name="3" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="109,89,122,255"/>
          <prop k="outline_color" v="75,60,85,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <!-- Agricultural - green -->
      <symbol name="4" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="138,201,38,255"/>
          <prop k="outline_color" v="95,140,25,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <!-- Office - cyan -->
      <symbol name="5" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="76,201,240,255"/>
          <prop k="outline_color" v="50,140,170,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <!-- Miscellaneous - gray -->
      <symbol name="6" type="fill" alpha="0.7" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="173,181,189,255"/>
          <prop k="outline_color" v="120,125,130,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.2"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <!-- Public / Utilities - blue -->
      <symbol name="7" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="39,125,161,255"/>
          <prop k="outline_color" v="25,85,110,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <!-- Church / Welfare - orange -->
      <symbol name="8" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="249,132,74,255"/>
          <prop k="outline_color" v="175,90,50,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <!-- Care / Health - sage -->
      <symbol name="9" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="144,190,109,255"/>
          <prop k="outline_color" v="100,130,75,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <!-- Recreational - teal -->
      <symbol name="10" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="67,170,139,255"/>
          <prop k="outline_color" v="45,115,95,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <!-- NULL / Unknown - light gray -->
      <symbol name="11" type="fill" alpha="0.5" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="222,226,230,255"/>
          <prop k="outline_color" v="170,175,180,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.1"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <labeling type="simple">
    <settings calloutType="simple">
      <text-style fieldName="SITE_ADDR" fontSize="8" fontFamily="Sans Serif" textColor="40,40,40,255" textOpacity="1">
        <text-buffer bufferDraw="1" bufferSize="0.8" bufferColor="255,255,255,210" bufferSizeUnits="MM"/>
      </text-style>
      <text-format wrapChar="" autoWrapLength="0"/>
      <placement placement="1" priority="5" centroidInside="1"/>
      <rendering scaleMin="0" scaleMax="5000" scaleVisibility="1" obstacle="1" obstacleFactor="1"/>
    </settings>
  </labeling>
</qgis>
